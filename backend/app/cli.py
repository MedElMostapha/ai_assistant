import click
from sqlalchemy import text
from werkzeug.security import generate_password_hash
from .models import db, User, Analysis, Document, ChatMessage, now


def register_cli(app):
    @app.cli.command('init-db')
    def init_db():
        """Create a fresh installation; use migrations for subsequent upgrades."""
        if db.engine.dialect.name == 'postgresql':
            db.session.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
            db.session.commit()
        db.create_all()
        click.echo('Database initialized.')

    @app.cli.command('create-admin')
    @click.option('--email', prompt=True)
    @click.option('--name', prompt=True)
    @click.password_option()
    def create_admin(email, name, password):
        from email_validator import validate_email
        email = validate_email(email, check_deliverability=False).normalized.lower()
        if len(password) < 12:
            raise click.ClickException('Password must contain at least 12 characters.')
        if db.session.scalar(db.select(User).where(User.email == email)):
            raise click.ClickException('User already exists; no changes made.')
        db.session.add(User(email=email, name=name, password_hash=generate_password_hash(password), role='admin', verified=True))
        db.session.commit()
        click.echo('Administrator created.')

    @app.cli.command('collect-garbage')
    def collect_garbage():
        from .jobs import collect_garbage
        collect_garbage()
        click.echo('Storage cleanup attempted.')

    @app.cli.command('recover-jobs')
    def recover_jobs():
        """Mark jobs older than 2 hours failed after a worker interruption."""
        from datetime import timedelta
        cutoff = now() - timedelta(hours=2)
        for model, states in [(Analysis, ['queued', 'running']), (Document, ['queued', 'extracting']), (ChatMessage, ['queued', 'running'])]:
            db.session.execute(db.update(model).where(model.updated_at < cutoff, model.status.in_(states)).values(status='failed', error='worker_interrupted'))
        db.session.commit()
        click.echo('Stale jobs can now be retried.')

    @app.cli.command('init-storage')
    def init_storage():
        """Initialize the private S3 bucket; retry while the S3 service starts."""
        import time
        from .storage import client, enforce_private_bucket
        from botocore.exceptions import ClientError, EndpointConnectionError
        if app.config['STORAGE_BACKEND'] != 's3':
            return
        for attempt in range(20):
            try:
                s3 = client()
                try:
                    s3.head_bucket(Bucket=app.config['S3_BUCKET'])
                except ClientError as exc:
                    if exc.response['Error']['Code'] not in ('404', 'NoSuchBucket'):
                        raise
                    kwargs = {'Bucket': app.config['S3_BUCKET']}
                    if app.config['S3_REGION'] != 'us-east-1':
                        kwargs['CreateBucketConfiguration'] = {'LocationConstraint': app.config['S3_REGION']}
                    s3.create_bucket(**kwargs)
                enforce_private_bucket()
                click.echo('Private storage ready.')
                return
            except (ClientError, EndpointConnectionError):
                if attempt == 19:
                    raise click.ClickException('Storage unavailable or access denied.')
                time.sleep(2)
