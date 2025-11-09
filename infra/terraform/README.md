# Terraform Infrastructure

This directory contains Terraform configurations for deploying PTCG Agents infrastructure.

## Prerequisites

- Terraform >= 1.0
- Cloud provider credentials configured
- Appropriate permissions for resource creation

## Usage

1. Initialize Terraform:
```bash
terraform init
```

2. Review the plan:
```bash
terraform plan
```

3. Apply the configuration:
```bash
terraform apply
```

## Notes

- The current configuration is a template and needs to be customized for your cloud provider
- Update variables and resource configurations based on your requirements
- Use Terraform Cloud or similar for state management in production
- Store sensitive values (passwords, API keys) in Terraform variables or secrets manager

