# Ultra cost-efficient deployment configuration
import os

# RDS Free Tier for maximum cost savings
# ✅ FREE for 12 months from AWS account creation:
# - 750 hours/month of db.t3.micro (24/7 free)
# - 20 GB storage (enough for thousands of users)
# - 20 GB backup storage
# - Single AZ deployment

# Lambda configuration for cost efficiency
LAMBDA_MEMORY = 512  # MB - right-size for our workload
LAMBDA_TIMEOUT = 30  # seconds - enough for DB queries + WhatsApp API
LAMBDA_RESERVED_CONCURRENCY = 10  # Prevent runaway costs

# Database connection pooling for Lambda
DB_POOL_SIZE = 1  # Single connection per Lambda instance
DB_MAX_OVERFLOW = 0  # No connection overflow
DB_POOL_TIMEOUT = 10  # Quick timeout for Lambda
DB_POOL_RECYCLE = 3600  # Recycle connections every hour

# Cost breakdown (monthly):
# 🆓 RDS PostgreSQL: $0 (free tier)
# 💰 Lambda: ~$0-5 (1M requests = $0.20)
# 💰 API Gateway: ~$3.50 per 1M requests
# 💰 Data transfer: ~$0-2

print("✅ ULTRA cost-efficient serverless configuration!")
print("💰 Expected monthly cost: $0-10 (first 12 months)")
print("🎯 After free tier: $15-25/month for moderate usage")
print("📈 Scales automatically, pay per use only")
