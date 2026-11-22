class IntegrationNotConfigured(RuntimeError):
    code = "INTEGRATION_NOT_CONFIGURED"


class DisabledAdapter:
    enabled = False

    def execute(self, *args, **kwargs):
        raise IntegrationNotConfigured(
            "Kết nối chưa được cấu hình; sử dụng tài khoản cục bộ hoặc CSV"
        )


class IdentityAdapter(DisabledAdapter):
    pass


class RosterAdapter(DisabledAdapter):
    pass


class GradeExportAdapter(DisabledAdapter):
    pass
