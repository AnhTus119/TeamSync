"""CLI for the same SQLite database used by the local server."""
import sys
from run import app

if __name__ == '__main__':
    with app.app_context():
        app.cli.main(args=sys.argv[1:],prog_name='python manage.py')
