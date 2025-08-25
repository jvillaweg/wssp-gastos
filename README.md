# 📱 WhatsApp Expense Tracker (WSSP)

A serverless WhatsApp bot for tracking personal expenses built with FastAPI, AWS Lambda, and PostgreSQL.

## 🏗️ Architecture

- **Backend**: FastAPI with SQLAlchemy ORM
- **Database**: PostgreSQL (AWS RDS)
- **Deployment**: AWS Lambda + API Gateway (via SAM)
- **WhatsApp Integration**: Meta Business API
- **Migrations**: Alembic for database schema management

## 📋 Prerequisites

- Python 3.11+
- AWS Account with CLI configured
- Meta Developer Account (for WhatsApp Business API)
- AWS SAM CLI
- Git

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/jvillaweg/wssp-gastos.git
cd wssp-gastos

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Local Development

```bash
# Set environment variables
export DATABASE_URL="postgresql://user:password@localhost:5432/wssp"
export META_VERIFY_TOKEN="your_verify_token"
export META_APP_SECRET="your_app_secret"
export META_ACCESS_TOKEN="your_access_token"
export META_PHONE_NUMBER_ID="your_phone_number_id"

# Run database migrations
python migrate.py

# Start local server
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/healthz` to verify the app is running.

## 🗄️ Database Management

### Migration Commands

```bash
# Apply all pending migrations
python migrate.py

# Create a new migration (after modifying models)
alembic revision --autogenerate -m "Description of changes"

# Check current migration status
alembic current

# View migration history
alembic history

# Rollback to previous migration
alembic downgrade -1
```

### Adding New Tables

1. **Update models** in `app/models.py`:
```python
class Expense(Base):
    __tablename__ = "expenses"
    expense_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    amount = Column(Numeric(10, 2))
    description = Column(Text)
    category = Column(String(50))
    created_at = Column(DateTime)
```

2. **Generate migration**:
```bash
alembic revision --autogenerate -m "Add expenses table"
```

3. **Apply migration**:
```bash
python migrate.py
```

## ☁️ AWS Deployment

### Prerequisites

1. **Install AWS SAM CLI**:
```bash
# Windows (using winget)
winget install Amazon.SAM-CLI

# macOS
brew install aws-sam-cli

# Linux
pip install aws-sam-cli
```

2. **Configure AWS credentials**:
```bash
aws configure
```

### Manual Deployment

```bash
# Build the application
sam build

# Deploy (first time - guided)
sam deploy --guided

# Deploy (subsequent times)
sam deploy --parameter-overrides \
  MetaVerifyToken=your_token \
  MetaAppSecret=your_secret \
  MetaAccessToken=your_access_token \
  MetaPhoneNumberId=your_phone_id \
  DatabasePassword=your_db_password
```

### Automated Deployment (GitHub Actions)

The project includes automated deployment via GitHub Actions that triggers on push to `main` branch.

#### Setup GitHub Secrets

Go to your repository settings → Secrets and variables → Actions, and add:

| Secret Name | Description |
|-------------|-------------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |
| `META_VERIFY_TOKEN` | WhatsApp verify token (you define this) |
| `META_APP_SECRET` | Meta app secret from developer console |
| `META_ACCESS_TOKEN` | Meta access token from developer console |
| `META_PHONE_NUMBER_ID` | WhatsApp phone number ID |
| `DATABASE_PASSWORD` | PostgreSQL master password (min 8 chars) |

#### Deploy

```bash
# Simply push to main branch
git add .
git commit -m "Deploy changes"
git push origin main
```

Monitor deployment progress in the "Actions" tab of your GitHub repository.

## 🔗 WhatsApp Configuration

### Getting Meta Credentials

1. **Create Meta App**:
   - Go to [Meta for Developers](https://developers.facebook.com/)
   - Create a new app → Business → WhatsApp Business Platform

2. **Configure Webhook**:
   - **Webhook URL**: `https://your-api-gateway-url/webhook/meta/whatsapp`
   - **Verify Token**: Use the same value as `META_VERIFY_TOKEN`
   - **Webhook Fields**: Select `messages`

3. **Get Required Values**:
   - `META_APP_SECRET`: App Dashboard → App Settings → Basic
   - `META_ACCESS_TOKEN`: WhatsApp → API Setup → Temporary token
   - `META_PHONE_NUMBER_ID`: WhatsApp → API Setup → Phone Number ID

### Testing Webhook

```bash
# Test verification endpoint
curl "https://your-api-gateway-url/webhook/meta/whatsapp?hub.mode=subscribe&hub.verify_token=your_token&hub.challenge=test"

# Should return: test

# Test health endpoint
curl "https://your-api-gateway-url/healthz"

# Should return: {"status": "ok"}
```

## 📁 Project Structure

```
wssp-gastos/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── models.py            # SQLAlchemy models
│   ├── database.py          # Database configuration
│   ├── message_handler.py   # WhatsApp message processing
│   ├── command_router.py    # Command routing logic
│   ├── wa_sender.py         # WhatsApp message sending
│   ├── session_manager.py   # User session management
│   ├── privacy_manager.py   # Privacy and consent handling
│   ├── rate_limiter.py      # Rate limiting
│   └── idempotency.py       # Duplicate message handling
├── alembic/
│   ├── versions/            # Database migrations
│   ├── env.py              # Alembic environment config
│   └── script.py.mako      # Migration template
├── .github/
│   └── workflows/
│       └── deploy.yml       # GitHub Actions deployment
├── alembic.ini             # Alembic configuration
├── template.yaml           # AWS SAM template
├── samconfig.toml          # SAM deployment config
├── lambda_handler.py       # Lambda entry point
├── migrate.py              # Migration runner script
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/webhook/meta/whatsapp` | WhatsApp webhook verification |
| POST | `/webhook/meta` | WhatsApp webhook events |
| GET | `/healthz` | Health check |
| GET | `/reports/summary` | Expense summaries |
| GET | `/export/csv` | CSV export |

## 🐛 Troubleshooting

### Common Issues

1. **Migration Errors**:
```bash
# Reset database (development only)
alembic downgrade base
python migrate.py
```

2. **WhatsApp Verification Failed**:
   - Check `META_VERIFY_TOKEN` matches in both Meta console and AWS
   - Verify webhook URL is correct
   - Check CloudFormation outputs for actual API Gateway URL

3. **Deployment Fails**:
```bash
# Clean up failed stack
aws cloudformation delete-stack --stack-name wssp-expense-tracker
aws cloudformation wait stack-delete-complete --stack-name wssp-expense-tracker

# Redeploy
sam deploy
```

4. **Database Connection Issues**:
   - Verify `DATABASE_URL` environment variable
   - Check RDS security groups allow Lambda access
   - Ensure database is in correct VPC subnets

### Getting Deployment URLs

After successful deployment, get your API endpoints:

```bash
# Get webhook URLs
aws cloudformation describe-stacks \
  --stack-name wssp-expense-tracker \
  --query 'Stacks[0].Outputs'
```

## 📚 Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp/business-management-api/)
- [Alembic Migrations](https://alembic.sqlalchemy.org/)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
- Check the [Issues](https://github.com/jvillaweg/wssp-gastos/issues) page
- Review CloudFormation stack events in AWS Console
- Check GitHub Actions logs for deployment issues
