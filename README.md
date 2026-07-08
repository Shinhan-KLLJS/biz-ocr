# OCR Lambda Service

Ncloud CLOVA General OCR을 호출해 사업자등록증 필드를 추출합니다. 로컬에서는 파일 경로를 직접 넘기고, AWS Lambda에서는 S3 객체 위치를 받아 `/tmp`에 다운로드한 뒤 동일한 OCR 파이프라인을 사용합니다.

### Local CLI

```powershell
python main.py .\data\368-88-03013.png --business-registration
python main.py .\data\368-88-03013.png --template-fields --output outputs\raw.json
```

### Lambda

Lambda handler:

```text
ocr_service.lambda_handler.handler
```

Direct invoke event:

```json
{
  "bucket": "your-bucket",
  "key": "incoming/368-88-03013.png"
}
```

S3 URI event:

```json
{
  "s3Uri": "s3://your-bucket/incoming/368-88-03013.png"
}
```

API Gateway/Lambda URL JSON body도 같은 payload를 사용할 수 있습니다.

Required Lambda environment variables:

```env
NCLOUD_OCR_API_URL=https://YOUR_INVOKE_URL.apigw.ntruss.com/custom/v1/YOUR_DOMAIN_ID/YOUR_DEPLOY_ID/general
NCLOUD_OCR_SECRET_KEY=YOUR_SECRET_KEY
NCLOUD_OCR_LANG=ko
NCLOUD_OCR_VERSION=V2
NCLOUD_OCR_TIMEOUT=60
NCLOUD_OCR_TEMPLATE_IDS=
```

Required IAM permissions:

- `s3:GetObject` for the input bucket or prefix
- CloudWatch Logs write permissions

### Package for Lambda

Create a zip package:

```powershell
.\scripts\package_lambda.ps1
```

The script creates:

```text
dist\lambda-deploy.zip
```

Use these Lambda settings:

```text
Runtime: Python 3.11 or Python 3.12
Handler: ocr_service.lambda_handler.handler
```

If your shell resolves `python` to a version that differs from the Lambda runtime, pass the intended interpreter:

```powershell
.\scripts\package_lambda.ps1 -Python python
```

Deploy the generated zip through the AWS Console, AWS CLI, or your IaC tool. The zip must include `requests`, because the Lambda runtime does not provide it by default.

### Validation

```powershell
python -m compileall main.py ocr_service tests
python -m unittest discover
python main.py --help
```
