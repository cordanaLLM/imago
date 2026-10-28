# Public & Private Cloud Generic Deployment Guide

`imago` images are multi-cloud portable and support all major public and private cloud environments out of the box.

## Supported Cloud Environments

Cloud-init is unconstrained and dynamically detects your hosting cloud provider:

- **OpenStack / Harvester**: Native `ConfigDrive` and OpenStack metadata service.
- **Amazon Web Services (AWS)**: EC2 IMDSv2 metadata service.
- **Google Cloud Platform (GCP)**: Compute Engine metadata service.
- **Microsoft Azure**: Azure metadata service.
- **Hetzner Cloud**: Hetzner Cloud metadata service.
- **Scaleway / DigitalOcean**: Standard cloud-init metadata interfaces.

## Launching on OpenStack via Glance

```bash
openstack image create "imago-base-generic" \
  --file imago-cloud-base-generic.qcow2 \
  --disk-format qcow2 \
  --container-format bare \
  --public
```

---

## Multi-Cloud Golden Image Governance

Following [ADR-0011](../adr/0011-enterprise-golden-image-compliance-and-lifecycle.md), deploying encrypted golden images across multi-account cloud environments requires explicit key management and metadata service configurations:

### 1. Amazon Web Services (AWS) KMS & Auto Scaling Grants

When sharing encrypted AMIs across AWS accounts, EBS snapshots must be encrypted with a Customer Managed Key (CMK). AWS-managed keys (`aws/ebs`) cannot be shared across account boundaries.

To enable target accounts to launch instances via Auto Scaling Groups without launch failures (`Client.InternalError`):

1. **Target Account KMS Grant**: Create a persistent KMS grant for the target account's Auto Scaling Service-Linked Role:

   ```bash
   aws kms create-grant \
     --region us-east-1 \
     --key-id "arn:aws:kms:us-east-1:192002000001:key/source-cmk-id" \
     --grantee-principal "arn:aws:iam::192002000002:role/aws-service-role/autoscaling.amazonaws.com/AWSServiceRoleForAutoScaling" \
     --operations Decrypt GenerateDataKeyWithoutPlainText CreateGrant DescribeKey ReEncryptFrom ReEncryptTo
   ```

2. **Mandatory IMDSv2**: Enforce token-backed metadata access with hop-count limits:
   - `http_tokens = "required"`
   - `http_put_response_hop_limit = 1`

### 2. Microsoft Azure Compute Gallery (ACG)

- Publish golden image definitions into a centralized Azure Compute Gallery (formerly Shared Image Gallery).
- Grant consumer subscriptions the `Compute Reader` and `Virtual Machine Contributor` roles.
- Automate geo-replication across operational regions while preserving regional data locality.

### 3. Google Cloud Platform (GCP) Cross-Project Images

- Maintain validated golden images in a dedicated central project (e.g., `corp-compute-images`).
- Grant consumer service accounts the `roles/compute.imageUser` IAM role on the central project.
- Deploy instances directly referencing the centralized image family to receive automated updates.
