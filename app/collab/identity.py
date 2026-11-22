"""Configured Google OIDC and short-lived room-scoped Jitsi credentials."""
import base64, hashlib, hmac, json, time, secrets
from flask import session, redirect, url_for, current_app
from . import bp
from .services import *


def google_client():
    cfg=current_app.config
    need(cfg.get('GOOGLE_CLIENT_ID') and cfg.get('GOOGLE_CLIENT_SECRET') and cfg.get('SSO_ALLOWED_DOMAINS'),
         'INTEGRATION_NOT_CONFIGURED','SSO chưa được cấu hình với miền email của trường',503)
    from authlib.integrations.flask_client import OAuth
    oauth=OAuth(current_app)
    return oauth.register('google',client_id=cfg['GOOGLE_CLIENT_ID'],client_secret=cfg['GOOGLE_CLIENT_SECRET'],
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope':'openid email profile'})


@bp.get('/auth/providers')
def providers():
    return {'data':{'google':bool(current_app.config.get('GOOGLE_CLIENT_ID') and
        current_app.config.get('GOOGLE_CLIENT_SECRET') and current_app.config.get('SSO_ALLOWED_DOMAINS'))}}


@bp.get('/auth/google')
def google_start():
    return google_client().authorize_redirect(url_for('teamwork.google_callback',_external=True),nonce=secrets.token_urlsafe(32))


def resolve_google_identity(info):
    email=info.get('email','').lower()
    allowed=current_app.config.get('SSO_ALLOWED_DOMAINS',[])
    need(info.get('email_verified') is True and email.rsplit('@',1)[-1] in allowed,
         'SSO_DOMAIN_FORBIDDEN','Cần email đã xác minh thuộc trường được cho phép',403)
    subject=info.get('sub')
    need(isinstance(subject,str) and subject,'SSO_INVALID','Thiếu định danh OIDC',403)
    identity=ExternalIdentity.query.filter_by(provider='google',subject=subject).first()
    if identity:
        u=get(User,identity.user_id)
    else:
        u=User.query.filter_by(email=email).first()
        need(u and u.role!='admin','ACCOUNT_NOT_PROVISIONED','Tài khoản phải được nhà trường cấp trước',403)
        need(not ExternalIdentity.query.filter_by(user_id=u.id,provider='google').first(),
             'SSO_IDENTITY_CONFLICT','Tài khoản đã gắn định danh khác',403)
        db.session.add(ExternalIdentity(user_id=u.id,provider='google',subject=subject))
    need(u.is_active and u.role!='admin','ACCOUNT_DISABLED','Tài khoản không khả dụng',403)
    return u


@bp.get('/auth/google/callback')
def google_callback():
    token=google_client().authorize_access_token()  # Authlib validates state, signature, issuer, audience and nonce.
    info=token.get('userinfo')
    need(isinstance(info,dict),'SSO_INVALID','Không đọc được định danh Google',403)
    u=resolve_google_identity(info)
    db.session.commit()
    session.clear()
    session['user_id']=u.id
    session['csrf']=secrets.token_urlsafe(32)
    return redirect('/home')


def meeting_credentials(m):
    cfg=current_app.config
    domain=cfg.get('JITSI_DOMAIN','')
    need(domain and re.fullmatch(r'[a-zA-Z0-9.-]+(?::[0-9]+)?',domain),
         'INTEGRATION_NOT_CONFIGURED','Chưa cấu hình máy chủ họp Jitsi',503)
    production=cfg.get('APP_ENV')=='production'
    need(not production or (cfg.get('JITSI_APP_ID') and cfg.get('JITSI_SECRET')),
         'INTEGRATION_NOT_CONFIGURED','Production yêu cầu Jitsi có xác thực JWT',503)
    result={'domain':domain,'room_name':m.room_name,'display_name':current_user().full_name,
            'demo_public_server':not bool(cfg.get('JITSI_SECRET')),'jwt':None}
    if cfg.get('JITSI_SECRET'):
        at=int(time.time())
        claims={'aud':cfg.get('JITSI_AUDIENCE','jitsi'),'iss':cfg.get('JITSI_APP_ID'),
            'sub':domain.split(':')[0],'room':m.room_name,'iat':at,'nbf':at-5,'exp':at+600,
            'context':{'user':{'id':str(current_user().id),'name':current_user().full_name,
                               'moderator':current_user().id==m.host_id}}}
        def b64(raw):return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()
        encoded=b64(json.dumps({'alg':'HS256','typ':'JWT'},separators=(',',':')).encode())+'.'+b64(json.dumps(claims,separators=(',',':')).encode())
        result['jwt']=encoded+'.'+b64(hmac.new(cfg['JITSI_SECRET'].encode(),encoded.encode(),hashlib.sha256).digest())
    return result
