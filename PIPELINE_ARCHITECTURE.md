# CI/CD Pipeline Architecture

## Overview

This document describes the GitHub Actions CI/CD pipeline architecture for the AWS Cloud Resume Challenge project.

## Architecture Principles

1. **Centralized Configuration**: All configuration values are stored in `.github/workflows/config.yaml`
2. **Reusable Components**: Composite actions for common operations (AWS credentials, stack outputs)
3. **Explicit Dependencies**: All workflow dependencies are properly enforced with `needs:`
4. **Separation of Concerns**: Infrastructure deployment separate from content updates
5. **Manual Control**: CloudFront deployment does not automatically trigger site uploads

## Configuration Management

### Centralized Config (`.github/workflows/config.yaml`)

All deployment configuration is centralized in a single reusable workflow:

- **AWS Region**: `us-east-1`
- **IAM Role Name**: `automated-deployments`
- **Stack Names**: All CloudFormation stack names
- **Lambda Function Name**: `visitors_tracker_function`
- **Domain Configuration**: `{your domain}` / `{your sub-domain}`

## Composite Actions

### `.github/actions/configure-aws/`

Configures AWS credentials using OIDC. Eliminates duplication across all workflows.

**Inputs:**
- `aws-region`: AWS region
- `role-arn`: IAM role ARN to assume
- `session-name`: Role session name (optional)

### `.github/actions/get-stack-output/`

Fetches CloudFormation stack outputs

**Inputs:**
- `stack-name`: CloudFormation stack name
- `output-key`: Output key to fetch

**Outputs:**
- `value`: The output value

## Deployment Workflows

### 1. S3 Stack (`deploy-s3-stack.yaml`)
**Purpose**: Deploy S3 bucket for Lambda sources and upload initial code

**Dependencies**: None (foundational)

**Triggers**:
- Manual via `main.yaml`
- Automatic on `cloudformation/s3-setup.yaml` changes

### 2. DynamoDB Stack (`deploy-dynamodb-stack.yaml`)
**Purpose**: Deploy DynamoDB table for visitor tracking

**Dependencies**: None (foundational)

**Triggers**:
- Manual via `main.yaml`
- Automatic on `cloudformation/dynamodb-setup.yaml` changes

### 3. Lambda Stack (`deploy-lambda-stack.yaml`)
**Purpose**: Deploy Lambda function CloudFormation stack

**Dependencies**: 
- S3 Stack (requires bucket for code)
- DynamoDB Stack (requires table name for IAM permissions)

**Triggers**:
- Manual via `main.yaml`
- Automatic on `cloudformation/lambda-setup.yaml` changes

### 4. Lambda Code (`deploy-lambda-code.yaml`)
**Purpose**: Update Lambda function code without redeploying stack

**Dependencies**: Lambda Stack (function must exist)

**Triggers**:
- Manual via `main.yaml` (runs after Lambda stack)
- Automatic on `lambda_handler.py` changes

### 5. API Gateway Stack (`deploy-api-gateway-stack.yaml`)
**Purpose**: Deploy API Gateway REST API

**Dependencies**: Lambda Stack (requires Lambda ARN)

**Triggers**:
- Manual via `main.yaml`
- Automatic on `cloudformation/api-gateway-setup.yaml` changes

### 6. CloudFront Stack (`deploy-cloudfront-stack.yaml`)
**Purpose**: Deploy CloudFront distribution with S3 and API Gateway origins

**Dependencies**: API Gateway Stack (imports domain name)

**Triggers**:
- Manual via `main.yaml`
- Automatic on `cloudformation/cloudfront-setup.yaml` changes

### 7. Upload Site Sources (`upload-site-sources.yaml`)
**Purpose**: Upload static website files to S3

**Dependencies**: CloudFront Stack (requires bucket name)

**Triggers**:
- Manual via `main.yaml`
- Automatic on changes to: `index.html`, `styles.css`, `visitors.js`, `images/**`

## Trigger Workflows

All trigger workflows follow a consistent pattern:

1. Load configuration from `config.yaml`
2. Call the appropriate deployment workflow with config values
3. Pass `AWS_ACCOUNT_ID` secret

### Automatic Triggers

| Workflow | Trigger Path | Action |
|----------|-------------|--------|
| `trigger-s3-on-change.yaml` | `cloudformation/s3-setup.yaml` | Deploy S3 stack |
| `trigger-dynamodb-on-change.yaml` | `cloudformation/dynamodb-setup.yaml` | Deploy DynamoDB stack |
| `trigger-lambda-on-change.yaml` | `cloudformation/lambda-setup.yaml` | Deploy Lambda stack |
| `trigger-lambda-code-on-change.yaml` | `lambda_handler.py` | Update Lambda code |
| `trigger-apigw-on-change.yaml` | `cloudformation/api-gateway-setup.yaml` | Deploy API Gateway |
| `trigger-cloudfront-on-change.yaml` | `cloudformation/cloudfront-setup.yaml` | Deploy CloudFront |
| `trigger-site-assets-on-change.yaml` | `index.html`, `styles.css`, `visitors.js`, `images/**` | Upload site files |

## Main Orchestration Workflow

The `main.yaml` workflow provides manual control over all deployments with proper dependency enforcement.

### Dependency Flow

```
LoadConfig
    ↓
    ├─→ RunBasicInfraSetup (S3)
    │       ↓
    ├─→ RunDynamoDBSetup
    │       ↓
    └─→ RunCreateLambdaStack ←─ (needs both S3 and DynamoDB)
            ↓
            ├─→ RunDeployLambdaCode
            │
            └─→ RunAPIGatewaySetup
                    ↓
                    └─→ RunCloudFrontSetup
                            ↓
                            └─→ UploadSiteSources
```

## CloudFormation Stack Dependencies

```
┌─────────────────────────────────────────────────────────────┐
│                    FOUNDATIONAL LAYER                        │
│  ┌──────────────┐              ┌──────────────┐            │
│  │ storage-stack│              │dynamodb-stack│            │
│  │  (S3 Bucket) │              │ (DDB Table)  │            │
│  └──────┬───────┘              └──────┬───────┘            │
└─────────┼──────────────────────────────┼───────────────────┘
          │                              │
          └──────────┬───────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    COMPUTE LAYER                             │
│              ┌──────────────┐                                │
│              │ lambda-stack │                                │
│              │  (Function)  │                                │
│              └──────┬───────┘                                │
└─────────────────────┼───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    API LAYER                                 │
│           ┌─────────────────┐                                │
│           │api-gateway-stack│                                │
│           │   (REST API)    │                                │
│           └────────┬────────┘                                │
└────────────────────┼─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    DISTRIBUTION LAYER                        │
│           ┌─────────────────┐                                │
│           │cloudfront-stack │                                │
│           │ (CDN + Website) │                                │
│           └────────┬────────┘                                │
└────────────────────┼─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    CONTENT LAYER                             │
│           ┌─────────────────┐                                │
│           │  Site Assets    │                                │
│           │   (S3 Upload)   │                                │
│           └─────────────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

## Setup Instructions

### Prerequisites

Before using the CI/CD pipeline, ensure you have:

1. AWS account with OIDC provider configured for GitHub Actions
2. IAM role named `automated-deployments` with appropriate permissions (you can use `/cloudformation/sample-gh-actions-deployment-role.yaml as a base to create a CloudFormation stack with necessary role)
3. Route53 hosted zone for your domain


### 1. Configure GitHub Secrets:
- `AWS_ACCOUNT_ID`
- `HOSTED_ZONE_ID`
- `API_GATEWAY_API_KEY`

### 2. Update Configuration

Edit `.github/workflows/config.yaml` to customize:
- AWS region
- Stack names
- Domain names
- Lambda function name

### 3. Deploy Infrastructure

Run the "Main Pipeline" workflow manually:

1. Go to Actions → Main Pipeline → Run workflow
2. Select which components to deploy:
   - Run S3 stack setup
   - Run DynamoDB setup
   - Run Lambda setup
   - Run API Gateway setup
   - Run CloudFront setup
   - Upload site sources (optional)
