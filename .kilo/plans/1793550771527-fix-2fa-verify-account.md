# Plan: Fix 2FA duplicate methods and account verification tracking

## Problem statement recap
1. In 2FA, same method can be added multiple times but shouldn't be. Fix it.
2. At verify account, after completing verification of both email and phone already, user can verify again. Want that after both email and phone verification are complete, button changes to "Verified" and account becomes verified.

## Current state analysis
- **2FA**: TwoFactorMethod has (user, method, destination, is_primary, is_verified). In TwoFactorEnrollView and TwoFactorSettingsView.add_method there is no check preventing duplicate method type (email/sms) for same user.
- **Verification**: VerifyAccountView allows verifying email or phone via OTP. When verified with purpose 'registration' it sets user.is_active=True. No tracking of which channels verified. The dashboard/navbar show "Verify Account" button/link unconditionally.

## Solution design

### 1) Prevent duplicate 2FA methods
Add checks to prevent adding the same method type more than once per user:
- `TwoFactorEnrollView.post()`: check if user already has TwoFactorMethod with same `method` and reject if exists.
- `TwoFactorSettingsView.post()` action `add_method`: same check.
- `Api2FAEnrollView.post()`: same check.
- Return appropriate error messages.

### 2) Track verification status and require both
Add fields to CustomUser model:
- `email_verified = BooleanField(default=False)`
- `phone_verified = BooleanField(default=False)`
- `account_verified = BooleanField(default=False)`

Update serializers to expose these fields.

When verifying:
- In `VerifyAccountView.verify_otp` (HTML): after successful verification, get `stored_channel` from session. Set `email_verified = True` if channel is email, `phone_verified = True` if sms/phone. If both verified (or both that exist are verified), set `account_verified = True`. Save user.
- In `ApiVerifyView.verify_otp` (API): similar logic.
- UI should reflect verified state.

### 3) Update UI to show verified state
- Dashboard template (`backend/templates/admin_panel/dashboard/index.html`): change "Verify Account" button to show "Verified" when `account_verified` (or both verified). 
- Navbar template (`backend/templates/admin_panel/includes/navbar.html`): similar change.

### 4) Migrations
Need to create migration for adding fields to CustomUser.

## Implementation steps
1. **Models** (`apps/accounts/models.py`): Add `email_verified`, `phone_verified`, `account_verified` to `CustomUser`
2. **Migrations**: Create migration (0003_add_verification_fields.py)
3. **Serializers** (`apps/accounts/serializers.py`): Add fields to `UserSerializer`
4. **Views - 2FA duplicate prevention**:
   - `TwoFactorEnrollView.post()`: check existing method of same type
   - `TwoFactorSettingsView.post()` action `add_method`: check existing method of same type  
   - `Api2FAEnrollView.post()`: check existing method of same type
5. **Views - Verification tracking**:
   - `VerifyAccountView.verify_otp()`: track verification per channel, update flags, set `account_verified` when both done
   - `ApiVerifyView.verify_otp()`: similar tracking
6. **Templates/UI**: Update dashboard and navbar to show verified state based on verification status

## Validation
- Try to add same 2FA method twice → prevented with error message
- Verify email, verify phone → both flags set, `account_verified` True, UI shows "Verified" state
- Cannot add duplicate method types
