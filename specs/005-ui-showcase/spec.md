# UI Showcase

## Current state

The repository has an EspoCRM-hosted React Web UI in `client/custom/ui/`, native EspoCRM surfaces in `client/custom/src/` and `client/custom/res/fusanhe/`, and a separate Android Compose client. There is no single offline entry point for reviewing these surfaces. CRM Docker is unavailable in the current local environment.

## User value

Review the existing UI from one folder without CRM credentials or production data, while retaining a clear distinction between runnable Web components, native EspoCRM pages, and Android screens.

## Requirements

- **FR-001**: `ui-showcase/` runs the repository's existing generated Web component bundle and CSS; it does not restyle or duplicate React screens.
- **FR-002**: The showcase navigates the Home, CRM, AI service, insights, five queue types, conversation, Account/Contact/Lead customer summaries, and draft/knowledge/outbound context summaries.
- **FR-003**: Fixtures are fictional and offline. All writes are blocked, and navigation stays within the showcase. The global outbound state is paused.
- **FR-004**: Login, native EspoCRM record pages and Android Compose screens are inventoried with source links and an explicit preview limitation; they are never represented as identical browser renders.
- **FR-005**: A single command and README explain launch, scope, source ownership, verification and removal.

## Acceptance

1. A local static server opens the showcase without Docker or network calls.
2. Each runnable Web screen mounts without a blank/error state and uses only fictional data.
3. Buttons that would write in CRM cannot change data or contact the backend.
4. Source catalogs cover all custom Web screen families and Android screen source files.

## Out of scope

Production deployment, API changes, real customer data, Android-to-Web porting, visual approval of native EspoCRM pages.
