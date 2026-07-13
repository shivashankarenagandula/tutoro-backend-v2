web: gunicorn config.wsgi --log-file -
release: python manage.py migrate && python manage.py loaddata mvp_seed_data && python manage.py create_admin
