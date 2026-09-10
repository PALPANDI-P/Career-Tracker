web: gunicorn "dashboard.app:create_app()" --bind 0.0.0.0:$PORT --workers 2 --threads 4
bot: python hourly_job_bot.py --daemon
