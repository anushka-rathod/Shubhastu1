/**
 * Shubhashtu Fashion - Admin Dashboard Management
 * Handles Order Status Updates, Product Forms, Reports Export & Settings.
 */

// Quick update order status
async function updateOrderStatus(orderId, newStatus) {
    if (!confirm(`Are you sure you want to update order #${orderId} status to "${newStatus}"?`)) {
        return;
    }

    try {
        const res = await fetch(`/admin/orders/update-status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                order_id: orderId,
                status: newStatus,
                comment: `Status updated to ${newStatus} from admin panel.`
            })
        });
        const data = await res.json();
        if (data.success) {
            alert('Order status updated successfully.');
            window.location.reload();
        } else {
            alert(data.message || 'Failed to update order status.');
        }
    } catch (err) {
        alert('Server communication error.');
    }
}

// Export orders table to CSV
function exportOrdersToCSV() {
    window.location.href = '/admin/orders/export-csv';
}

// Toggle coupon active state
async function toggleCoupon(couponId) {
    try {
        const res = await fetch(`/admin/coupons/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ coupon_id: couponId })
        });
        const data = await res.json();
        if (data.success) {
            window.location.reload();
        }
    } catch (err) {
        alert('Could not update coupon.');
    }
}

// Delete coupon
async function deleteCoupon(couponId) {
    if (!confirm('Are you sure you want to permanently delete this coupon?')) return;
    try {
        const res = await fetch(`/admin/coupons/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ coupon_id: couponId })
        });
        const data = await res.json();
        if (data.success) {
            window.location.reload();
        }
    } catch (err) {
        alert('Could not delete coupon.');
    }
}

// Toggle review approval
async function toggleReviewApproval(reviewId) {
    try {
        const res = await fetch(`/admin/reviews/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ review_id: reviewId })
        });
        const data = await res.json();
        if (data.success) {
            window.location.reload();
        }
    } catch (err) {
        alert('Could not update review.');
    }
}

// Delete review
async function deleteReview(reviewId) {
    if (!confirm('Delete this customer review?')) return;
    try {
        const res = await fetch(`/admin/reviews/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ review_id: reviewId })
        });
        const data = await res.json();
        if (data.success) {
            window.location.reload();
        }
    } catch (err) {
        alert('Could not delete review.');
    }
}

// Delete product
async function deleteProduct(productId) {
    if (!confirm('Are you sure you want to permanently delete this product? This action cannot be undone.')) return;
    try {
        const res = await fetch(`/admin/products/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: productId })
        });
        const data = await res.json();
        if (data.success) {
            window.location.reload();
        } else {
            alert(data.message || 'Could not delete product.');
        }
    } catch (err) {
        alert('Failed to connect to server.');
    }
}

// Delete customer
async function deleteCustomer(customerId, customerName) {
    const label = customerName ? `customer "${customerName}"` : `customer #${customerId}`;
    if (!confirm(`Are you sure you want to permanently delete ${label}? Their profile and account login will be removed.`)) return;
    try {
        const res = await fetch(`/admin/customers/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ customer_id: customerId })
        });
        const data = await res.json();
        if (data.success) {
            window.location.reload();
        } else {
            alert(data.message || 'Could not delete customer.');
        }
    } catch (err) {
        alert('Could not delete customer. Server communication error.');
    }
}

// Delete order
async function deleteOrder(orderId, orderNumber) {
    const label = orderNumber ? `Order #${orderNumber}` : `order #${orderId}`;
    if (!confirm(`Are you sure you want to permanently delete ${label}? All order items and status history will be removed.`)) return;
    try {
        const res = await fetch(`/admin/orders/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_id: orderId })
        });
        const data = await res.json();
        if (data.success) {
            window.location.reload();
        } else {
            alert(data.message || 'Could not delete order.');
        }
    } catch (err) {
        alert('Could not delete order. Server communication error.');
    }
}

