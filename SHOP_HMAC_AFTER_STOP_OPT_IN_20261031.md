# Verify isolated Sandbox webhook after test-purchase preview shutdown

After restoring BIGPAW_SHOP_STAGE_PREVIEW_ENABLED=0 and deploying successfully, check the NEW isolated Square Sandbox webhook signature boundary one time. Prove valid HMAC for a fake unmatched order is safely deferred, invalid HMAC is denied, invalid environment is denied. Strictly no Square card/payment, hosted checkout, real event, email, old Sandbox or production mutation. No retries of provider operations.
