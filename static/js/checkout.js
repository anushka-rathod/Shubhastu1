/**
 * Shubhashtu Fashion - Checkout Experience
 * Handles Live Address & Pincode Resolution, Dynamic Shipping Calculation,
 * Coupon Application, Razorpay Gateway Integration, and Cash on Delivery.
 */

let currentOrderState = {
    subtotal: 0,
    shippingFee: 0,
    codFee: 0,
    discount: 0,
    total: 0,
    couponCode: '',
    paymentMethod: 'razorpay',
    isExpress: false,
    pincode: '',
    city: '',
    state: ''
};

// Initialize checkout on page load
function initCheckout(initialCart) {
    currentOrderState.subtotal = initialCart.subtotal || 0;
    currentOrderState.shippingFee = initialCart.shipping_fee || 0;
    currentOrderState.total = initialCart.total || initialCart.subtotal;
    
    // Attach listener to PIN code input
    const pincodeInput = document.getElementById('shipping_pincode');
    if (pincodeInput) {
        pincodeInput.addEventListener('input', (e) => {
            const pin = e.target.value.replace(/\D/g, '').slice(0, 6);
            e.target.value = pin;
            if (pin.length === 6) {
                onPincodeEntered(pin);
            }
        });
    }

    // Attach listener to payment method radio
    const paymentRadios = document.querySelectorAll('input[name="payment_method"]');
    paymentRadios.forEach(r => {
        r.addEventListener('change', (e) => {
            currentOrderState.paymentMethod = e.target.value;
            recalculateTotals();
        });
    });

    // Check express delivery toggle if present
    const expressToggle = document.getElementById('express_delivery_toggle');
    if (expressToggle) {
        expressToggle.addEventListener('change', (e) => {
            currentOrderState.isExpress = e.target.checked;
            if (currentOrderState.pincode && currentOrderState.pincode.length === 6) {
                onPincodeEntered(currentOrderState.pincode);
            }
        });
    }

    recalculateTotals();
}

// When 6-digit PIN code is entered
async function onPincodeEntered(pincode) {
    const feedbackEl = document.getElementById('pincode-feedback');
    const cityInput = document.getElementById('shipping_city');
    const stateInput = document.getElementById('shipping_state');

    if (feedbackEl) {
        feedbackEl.innerHTML = `<span class="text-xs text-gray-500"><i class="fa-solid fa-spinner fa-spin mr-1"></i> Checking serviceability for ${pincode}...</span>`;
    }

    try {
        const isCod = currentOrderState.paymentMethod === 'cod';
        const res = await fetch(`/api/shipping/calculate?pincode=${pincode}&subtotal=${currentOrderState.subtotal}&express=${currentOrderState.isExpress ? 1 : 0}&cod=${isCod ? 1 : 0}`);
        const data = await res.json();

        if (data.serviceable) {
            currentOrderState.pincode = pincode;
            currentOrderState.shippingFee = data.shipping_fee;
            currentOrderState.codFee = isCod ? (data.cod_fee || 0) : 0;
            currentOrderState.city = data.city;
            currentOrderState.state = data.state;

            if (cityInput && !cityInput.value) cityInput.value = data.city;
            if (stateInput && !stateInput.value) stateInput.value = data.state;

            if (feedbackEl) {
                const badge = data.is_free_shipping ? '<span class="text-emerald-700 font-bold">FREE Delivery</span>' : `Delivery: ${formatINR(data.shipping_fee)}`;
                feedbackEl.innerHTML = `
                    <div class="mt-2 p-2 bg-emerald-50 border border-emerald-200 rounded text-xs text-emerald-900">
                        <i class="fa-solid fa-check-circle text-emerald-600 mr-1"></i> Serviceable • ${badge} • ETA: <strong>${data.estimated_days}</strong> (${data.estimated_date})
                    </div>
                `;
            }
            recalculateTotals();
        } else {
            if (feedbackEl) {
                feedbackEl.innerHTML = `<div class="mt-2 p-2 bg-rose-50 border border-rose-200 rounded text-xs text-rose-700"><i class="fa-solid fa-triangle-exclamation mr-1"></i> ${data.message || 'PIN code unserviceable.'}</div>`;
            }
        }
    } catch (err) {
        console.error(err);
    }
}

// Recalculate summary sidebar
function recalculateTotals() {
    const isCod = currentOrderState.paymentMethod === 'cod';
    const effectiveCodFee = isCod ? currentOrderState.codFee : 0;
    const finalTotal = Math.max(0, currentOrderState.subtotal - currentOrderState.discount + currentOrderState.shippingFee + effectiveCodFee);
    currentOrderState.total = Math.round(finalTotal * 100) / 100;

    const subtotalEl = document.getElementById('summary-subtotal');
    const shippingEl = document.getElementById('summary-shipping');
    const discountEl = document.getElementById('summary-discount');
    const codFeeRow = document.getElementById('summary-cod-fee-row');
    const codFeeEl = document.getElementById('summary-cod-fee');
    const totalEl = document.getElementById('summary-total');

    if (subtotalEl) subtotalEl.textContent = formatINR(currentOrderState.subtotal);
    
    if (shippingEl) {
        if (currentOrderState.shippingFee === 0) {
            shippingEl.innerHTML = `<span class="text-emerald-700 font-bold uppercase">Free</span>`;
        } else {
            shippingEl.textContent = formatINR(currentOrderState.shippingFee);
        }
    }

    if (discountEl) {
        if (currentOrderState.discount > 0) {
            discountEl.textContent = `-${formatINR(currentOrderState.discount)}`;
            discountEl.parentElement.classList.remove('hidden');
        } else {
            discountEl.parentElement.classList.add('hidden');
        }
    }

    if (codFeeRow && codFeeEl) {
        if (isCod && effectiveCodFee > 0) {
            codFeeEl.textContent = formatINR(effectiveCodFee);
            codFeeRow.classList.remove('hidden');
        } else {
            codFeeRow.classList.add('hidden');
        }
    }

    if (totalEl) totalEl.textContent = formatINR(currentOrderState.total);
}

// Apply Coupon Code
async function applyCoupon() {
    const codeInput = document.getElementById('coupon_code_input');
    const feedbackEl = document.getElementById('coupon-feedback');
    if (!codeInput) return;

    const code = codeInput.value.trim().toUpperCase();
    if (!code) {
        showToast('Please enter a coupon code', 'error');
        return;
    }

    try {
        const res = await fetch('/api/coupon/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code, subtotal: currentOrderState.subtotal })
        });
        const data = await res.json();

        if (data.valid) {
            currentOrderState.discount = data.discount;
            currentOrderState.couponCode = data.code;
            showToast(data.message, 'success');

            if (feedbackEl) {
                feedbackEl.innerHTML = `
                    <div class="mt-2 flex items-center justify-between p-2 bg-emerald-50 border border-emerald-200 rounded text-xs text-emerald-800">
                        <span><i class="fa-solid fa-tag text-emerald-600 mr-1"></i> Coupon <strong>${data.code}</strong> applied (-${formatINR(data.discount)})</span>
                        <button type="button" onclick="removeCoupon()" class="text-rose-600 hover:text-rose-800 font-bold ml-2">Remove</button>
                    </div>
                `;
            }
            recalculateTotals();
        } else {
            showToast(data.message || 'Invalid coupon code', 'error');
            if (feedbackEl) {
                feedbackEl.innerHTML = `<span class="text-xs text-rose-600">${data.message}</span>`;
            }
        }
    } catch (err) {
        showToast('Error applying coupon.', 'error');
    }
}

// Remove Coupon
function removeCoupon() {
    currentOrderState.discount = 0;
    currentOrderState.couponCode = '';
    const codeInput = document.getElementById('coupon_code_input');
    const feedbackEl = document.getElementById('coupon-feedback');
    if (codeInput) codeInput.value = '';
    if (feedbackEl) feedbackEl.innerHTML = '';
    showToast('Coupon removed', 'success');
    recalculateTotals();
}

// Place Order Form Submission
async function handleCheckoutSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const submitBtn = document.getElementById('place-order-btn');

    // Collect field values
    const customer_name = form.customer_name.value.trim();
    const customer_email = form.customer_email.value.trim();
    const customer_phone = form.customer_phone.value.trim();
    const shipping_address_line1 = form.shipping_address_line1.value.trim();
    const shipping_address_line2 = form.shipping_address_line2 ? form.shipping_address_line2.value.trim() : '';
    const shipping_landmark = form.shipping_landmark ? form.shipping_landmark.value.trim() : '';
    const shipping_city = form.shipping_city.value.trim();
    const shipping_state = form.shipping_state.value.trim();
    const shipping_pincode = form.shipping_pincode.value.trim();
    const customer_notes = form.customer_notes ? form.customer_notes.value.trim() : '';
    const payment_method = currentOrderState.paymentMethod;

    if (!customer_name || !customer_email || !customer_phone || !shipping_address_line1 || !shipping_city || !shipping_state || !shipping_pincode) {
        showToast('Please fill in all required shipping address fields.', 'error');
        return;
    }

    if (!/^\d{10}$/.test(customer_phone.replace(/\D/g, ''))) {
        showToast('Please enter a valid 10-digit mobile number.', 'error');
        return;
    }

    if (!/^\d{6}$/.test(shipping_pincode)) {
        showToast('Please enter a valid 6-digit PIN code.', 'error');
        return;
    }

    // Disable button and show spinner
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-2"></i> Processing Order...`;
    }

    const payload = {
        customer_name,
        customer_email,
        customer_phone,
        shipping_address_line1,
        shipping_address_line2,
        shipping_landmark,
        shipping_city,
        shipping_state,
        shipping_pincode,
        customer_notes,
        payment_method,
        coupon_code: currentOrderState.couponCode,
        is_express: currentOrderState.isExpress
    };

    // Branch: Cash on Delivery vs Online (Razorpay)
    if (payment_method === 'cod') {
        try {
            const res = await fetch('/api/checkout/place-cod-order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                window.location.href = `/order-success/${data.order_number}`;
            } else {
                showToast(data.message || 'Could not place order.', 'error');
                resetSubmitButton(submitBtn);
            }
        } catch (err) {
            showToast('Network error while placing order.', 'error');
            resetSubmitButton(submitBtn);
        }
    } else {
        // Razorpay Payment Flow
        try {
            const res = await fetch('/api/checkout/razorpay/create-order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();

            if (!data.success) {
                if (!data.configured) {
                    // Informative message when Razorpay keys are not yet configured
                    showToast(data.error || 'Razorpay credentials not yet configured.', 'error');
                    alert("Razorpay API credentials have not been configured yet.\n\nTo enable online payments:\n1. Open your .env file or go to Admin Dashboard > Payment Settings.\n2. Add your RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.\n\nIn the meantime, you can select 'Cash on Delivery (COD)' to place your test order!");
                } else {
                    showToast(data.error || 'Could not initiate Razorpay order.', 'error');
                }
                resetSubmitButton(submitBtn);
                return;
            }

            // Launch Razorpay Modal
            const options = {
                key: data.key_id,
                amount: data.amount_paise,
                currency: data.currency || 'INR',
                name: 'Shubhashtu Fashion',
                description: `Payment for Order #${data.order_number}`,
                image: window.location.origin + '/static/images/logo.jpg',
                order_id: data.razorpay_order_id,
                handler: async function (response) {
                    // Payment successful on client side; verify cryptographically on server
                    submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-2"></i> Verifying Payment...`;
                    try {
                        const verifyRes = await fetch('/api/checkout/razorpay/verify', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                order_id: data.internal_order_id,
                                razorpay_order_id: response.razorpay_order_id,
                                razorpay_payment_id: response.razorpay_payment_id,
                                razorpay_signature: response.razorpay_signature
                            })
                        });
                        const verifyData = await verifyRes.json();
                        if (verifyData.success) {
                            window.location.href = `/order-success/${data.order_number}`;
                        } else {
                            showToast(verifyData.error || 'Payment verification failed.', 'error');
                            resetSubmitButton(submitBtn);
                        }
                    } catch (err) {
                        showToast('Error verifying payment with server.', 'error');
                        resetSubmitButton(submitBtn);
                    }
                },
                prefill: {
                    name: customer_name,
                    email: customer_email,
                    contact: customer_phone
                },
                theme: {
                    color: '#c59b27'
                },
                modal: {
                    ondismiss: function () {
                        showToast('Payment cancelled by user.', 'error');
                        resetSubmitButton(submitBtn);
                    }
                }
            };

            const rzp = new Razorpay(options);
            rzp.on('payment.failed', function (response) {
                showToast(`Payment Failed: ${response.error.description}`, 'error');
                resetSubmitButton(submitBtn);
            });
            rzp.open();

        } catch (err) {
            showToast('Could not initiate online payment.', 'error');
            resetSubmitButton(submitBtn);
        }
    }
}

function resetSubmitButton(btn) {
    if (!btn) return;
    btn.disabled = false;
    btn.innerHTML = `<i class="fa-solid fa-lock mr-2"></i> Complete Order`;
}

