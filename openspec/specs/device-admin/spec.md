# device-admin Specification

## Purpose
TBD - created by archiving change document-device-admin-api. Update Purpose after archive.
## Requirements
### Requirement: Document Device Admin create/list/update endpoints
Docs MUST describe the admin endpoints (`POST /v1/device-admin/macs`, `GET /v1/device-admin/macs`, `PATCH /v1/device-admin/macs/{mac}`) with request/response schema, header requirements, and examples.

#### Scenario: Create device doc
- **WHEN** someone reads `docs/api/device-admin.md`
- **THEN** they see the payload schema (`mac`, `status`, `collect_enabled`, `ingress_config`, etc.), response structure (`DeviceResponse`), and cURL/JS samples

#### Scenario: List/update doc
- **WHEN** the doc covers list/update
- **THEN** it explains optional query `status`, MAC path param (upper-case requirement), and response fields

### Requirement: Error codes & auth guidance
Docs MUST include a table of error codes (`DEVICE_CONFLICT`, `DEVICE_NOT_FOUND`, `UNAUTHORIZED`, `INTERNAL_ERROR`) with HTTP status & typical causes, and remind clients to send `Authorization: Bearer <token>`.

#### Scenario: QA checks error table
- **WHEN** QA needs to simulate failure
- **THEN** they can find error names, HTTP codes, and trigger conditions

### Requirement: Mention MAC normalization & subscription behavior
Docs MUST note that MAC addresses are upper-cased/trimmed, and that create/update operations trigger `subscription_manager.apply_device`.

#### Scenario: Integrator references doc
- **WHEN** integrator reads doc
- **THEN** they know MAC must be uppercase and that changes may restart subscriptions

