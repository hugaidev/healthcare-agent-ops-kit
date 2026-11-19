# Reference infrastructure for a PHI-handling service. Illustrative: review against your own
# account structure, network design and compliance requirements before use.
# Validated by the repository's own review rules (opskit-review scan infra).

terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "environment" {
  type        = string
  description = "Deployment environment (staging, production)."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for the database. No public routes."
}

variable "app_security_group_id" {
  type        = string
  description = "Security group of the application tier allowed to reach the database."
}

resource "aws_kms_key" "phi" {
  description             = "PHI encryption key (${var.environment})"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_db_subnet_group" "main" {
  name       = "ops-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "db" {
  name        = "ops-db-${var.environment}"
  description = "Database access from the application tier only"

  ingress {
    description     = "PostgreSQL from application tier"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.app_security_group_id]
  }
}

resource "aws_db_instance" "main" {
  identifier                      = "ops-${var.environment}"
  engine                          = "postgres"
  instance_class                  = "db.t4g.medium"
  allocated_storage               = 50
  db_subnet_group_name            = aws_db_subnet_group.main.name
  vpc_security_group_ids          = [aws_security_group.db.id]
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.phi.arn
  publicly_accessible             = false
  backup_retention_period         = 35
  deletion_protection             = true
  multi_az                        = true
  iam_database_authentication_enabled = true
  enabled_cloudwatch_logs_exports = ["postgresql"]
  username                        = "ops_admin"
  manage_master_user_password     = true
}

resource "aws_s3_bucket" "audit" {
  bucket              = "ops-audit-${var.environment}"
  object_lock_enabled = true
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket                  = aws_s3_bucket.audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.phi.arn
    }
  }
}

resource "aws_s3_bucket_object_lock_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    default_retention {
      mode  = "COMPLIANCE"
      years = 6 # HIPAA documentation retention, 45 CFR 164.316(b)(2)
    }
  }
}
