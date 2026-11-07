/**
 * Shubhashtu Fashion - Main Frontend Interactions
 * Handles Mini Cart Drawer, Wishlist, Predictive Search, Toast System & Pincode Checker.
 */

// Toast notification helper
function showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icon = type === 'success' ? 'fa-circle-check text-emerald-500' : 'fa-circle-exclamation text-rose-500';
    
    toast.innerHTML = `
        <div class="flex items-center gap-3">
            <i class="fa-solid ${icon} text-lg"></i>
            <span class="text-sm font-medium text-gray-800">${message}</span>
        </div>
        <button onclick="this.parentElement.remove()" class="text-gray-400 hover:text-gray-600 text-sm ml-2">
            <i class="fa-solid fa-xmark"></i>
        </button>
    `;

    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// Format INR currency
function formatINR(amount) {
    const num = Number(amount) || 0;
    return '₹' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ----------------- Cart Drawer Management -----------------
function toggleCartDrawer(open = null) {
    const drawer = document.getElementById('cart-drawer');
    const backdrop = document.getElementById('cart-drawer-backdrop');
    if (!drawer || !backdrop) return;

    const isOpen = !drawer.classList.contains('translate-x-full');
    const shouldOpen = open !== null ? open : !isOpen;

    if (shouldOpen) {
        backdrop.classList.remove('hidden');
        requestAnimationFrame(() => {
            backdrop.classList.remove('opacity-0');
            drawer.classList.remove('translate-x-full');
        });
        refreshCartDrawer();
    } else {
        drawer.classList.add('translate-x-full');
        backdrop.classList.add('opacity-0');
        setTimeout(() => backdrop.classList.add('hidden'), 300);
    }
}

async function refreshCartDrawer() {
    try {
        const res = await fetch('/api/cart');
        const data = await res.json();
        renderCartUI(data);
    } catch (err) {
        console.error("Cart refresh failed:", err);
    }
}

function renderCartUI(cart) {
    // Update badge count
    const badges = document.querySelectorAll('.cart-badge-count');
    badges.forEach(b => {
        b.textContent = cart.item_count || 0;
        b.style.display = cart.item_count > 0 ? 'inline-flex' : 'none';
    });

    const itemsContainer = document.getElementById('cart-drawer-items');
    const emptyNotice = document.getElementById('cart-drawer-empty');
    const footer = document.getElementById('cart-drawer-footer');
    const subtotalEl = document.getElementById('cart-drawer-subtotal');
    const savingsEl = document.getElementById('cart-drawer-savings');
    const freeShippingProgress = document.getElementById('free-shipping-progress');
    const freeShippingText = document.getElementById('free-shipping-text');

    if (!itemsContainer) return;

    if (!cart.items || cart.items.length === 0) {
        itemsContainer.innerHTML = '';
        if (emptyNotice) emptyNotice.classList.remove('hidden');
        if (footer) footer.classList.add('hidden');
        return;
    }

    if (emptyNotice) emptyNotice.classList.add('hidden');
    if (footer) footer.classList.remove('hidden');

    if (subtotalEl) subtotalEl.textContent = formatINR(cart.subtotal);
    if (savingsEl) {
        savingsEl.textContent = cart.total_savings > 0 ? `You save ${formatINR(cart.total_savings)}!` : '';
        savingsEl.style.display = cart.total_savings > 0 ? 'block' : 'none';
    }

    // Free shipping threshold (default ₹999)
    const threshold = cart.free_shipping_threshold || 999;
    const remaining = Math.max(0, threshold - cart.subtotal);
    if (freeShippingProgress && freeShippingText) {
        const pct = Math.min(100, (cart.subtotal / threshold) * 100);
        freeShippingProgress.style.width = `${pct}%`;
        if (remaining === 0) {
            freeShippingText.innerHTML = `🎉 <strong>Congratulations!</strong> You get FREE standard shipping!`;
        } else {
            freeShippingText.innerHTML = `Add <strong>${formatINR(remaining)}</strong> more to get <strong>FREE Shipping</strong>!`;
        }
    }

    // Render items list
    itemsContainer.innerHTML = cart.items.map(item => `
        <div class="flex gap-4 p-4 border-b border-rose-100 hover:bg-rose-50/40 transition">
            <img src="${item.primary_image || '/static/images/logo.jpg'}" alt="${item.name}" class="w-18 h-20 object-cover rounded-md border border-rose-200">
            <div class="flex-1 min-w-0">
                <a href="/product/${item.slug}" class="text-sm font-semibold text-gray-900 hover:text-gold line-clamp-1">${item.name}</a>
                <p class="text-xs text-gray-500 mt-0.5">Size: <span class="font-medium text-gray-700">${item.selected_size || 'Free Size'}</span></p>
                <div class="flex items-center gap-2 mt-2">
                    <span class="text-sm font-bold text-gray-900">${formatINR(item.price)}</span>
                    ${item.mrp > item.price ? `<span class="text-xs text-gray-400 line-through">${formatINR(item.mrp)}</span>` : ''}
                </div>
                <div class="flex items-center justify-between mt-3">
                    <div class="inline-flex items-center border border-gray-300 rounded-md bg-white">
                        <button onclick="updateCartItemQty(${item.id}, ${item.quantity - 1})" class="px-2 py-0.5 text-xs text-gray-600 hover:bg-gray-100 rounded-l">
                            <i class="fa-solid fa-minus"></i>
                        </button>
                        <span class="px-2.5 py-0.5 text-xs font-semibold text-gray-800">${item.quantity}</span>
                        <button onclick="updateCartItemQty(${item.id}, ${item.quantity + 1})" class="px-2 py-0.5 text-xs text-gray-600 hover:bg-gray-100 rounded-r">
                            <i class="fa-solid fa-plus"></i>
                        </button>
                    </div>
                    <button onclick="removeCartItem(${item.id})" class="text-xs text-rose-500 hover:text-rose-700 font-medium">
                        <i class="fa-regular fa-trash-can mr-1"></i> Remove
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

// Add product to cart via API
async function addToCart(productId, quantity = 1, size = null, color = '', openDrawer = true) {
    try {
        const body = { product_id: productId, quantity: Number(quantity) || 1, size: size || 'Free Size', color: color };
        const res = await fetch('/api/cart/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (data.success) {
            showToast('Item added to your shopping bag!', 'success');
            if (openDrawer) {
                toggleCartDrawer(true);
            } else {
                refreshCartDrawer();
            }
        } else {
            showToast(data.message || 'Could not add to cart.', 'error');
        }
    } catch (err) {
        showToast('Error connecting to store.', 'error');
    }
}

// Update cart quantity
async function updateCartItemQty(cartItemId, newQty) {
    try {
        const res = await fetch('/api/cart/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cart_item_id: cartItemId, quantity: newQty })
        });
        const data = await res.json();
        if (data.success) {
            refreshCartDrawer();
            // If on cart page, reload or refresh
            if (window.location.pathname === '/cart') {
                window.location.reload();
            }
        }
    } catch (err) {
        console.error(err);
    }
}

// ----------------- Pure WhatsApp Order Generator -----------------
async function checkoutBagViaWhatsApp(supportPhone = null) {
    try {
        const res = await fetch('/api/cart');
        const cart = await res.json();
        if (!cart.items || cart.items.length === 0) {
            showToast('Your shopping bag is empty! Add items first.', 'error');
            return;
        }

        const phone = supportPhone || window.STORE_WHATSAPP || '919876543210';
        let itemsList = '';
        cart.items.forEach((item, index) => {
            const size = item.selected_size ? `(${item.selected_size})` : '';
            const price = Number(item.item_total || item.total_price || (item.price * item.quantity)).toFixed(2);
            itemsList += `${index + 1}. *${item.name}* ${size} x ${item.quantity} - ₹${price}\n`;
        });

        const threshold = cart.free_shipping_threshold || 999;
        const deliveryText = cart.subtotal >= threshold ? 'FREE' : '₹70.00 Standard Delivery';
        const total = cart.subtotal >= threshold ? cart.subtotal : (cart.subtotal + 70.0);

        const text = `Namaste Shubhashtu Fashion! 🙏\n\nI want to place an order for my shopping bag:\n\n${itemsList}\n📦 *Total Items:* ${cart.item_count}\n💵 *Subtotal:* ₹${Number(cart.subtotal).toFixed(2)}\n🚚 *Delivery:* ${deliveryText}\n💰 *Total Payable:* ₹${Number(total).toFixed(2)}\n\nPlease confirm availability and share your UPI QR code / GPay details to complete my payment. Thank you!`;

        const waUrl = `https://wa.me/${phone}?text=${encodeURIComponent(text)}`;
        window.open(waUrl, '_blank');
    } catch (e) {
        console.error("WhatsApp checkout error:", e);
        showToast('Could not initiate WhatsApp order. Please try again.', 'error');
    }
}

// Remove from cart
async function removeCartItem(cartItemId) {
    try {
        const res = await fetch('/api/cart/remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cart_item_id: cartItemId })
        });
        const data = await res.json();
        if (data.success) {
            showToast('Item removed from cart', 'success');
            refreshCartDrawer();
            if (window.location.pathname === '/cart') {
                window.location.reload();
            }
        }
    } catch (err) {
        console.error(err);
    }
}

// ----------------- Wishlist Management -----------------
async function toggleWishlist(productId, btnElement) {
    try {
        const res = await fetch('/api/wishlist/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: productId })
        });
        const data = await res.json();
        if (data.success) {
            const isAdded = data.added;
            showToast(isAdded ? 'Added to your Wishlist!' : 'Removed from Wishlist', 'success');
            if (btnElement) {
                const icon = btnElement.querySelector('i');
                if (icon) {
                    if (isAdded) {
                        icon.classList.remove('fa-regular');
                        icon.classList.add('fa-solid', 'text-rose-600');
                    } else {
                        icon.classList.remove('fa-solid', 'text-rose-600');
                        icon.classList.add('fa-regular');
                    }
                }
            }
            // Update wishlist badge count
            const wBadges = document.querySelectorAll('.wishlist-badge-count');
            wBadges.forEach(b => {
                b.textContent = data.count || 0;
                b.style.display = data.count > 0 ? 'inline-flex' : 'none';
            });

            // If on wishlist page and removed, remove card
            if (!isAdded && window.location.pathname === '/wishlist') {
                const card = btnElement.closest('.product-card');
                if (card) card.remove();
            }
        }
    } catch (err) {
        showToast('Could not update wishlist.', 'error');
    }
}

// ----------------- Pincode Delivery Estimator -----------------
async function checkPincodeServiceability(pincode, resultElementId, subtotal = 1000) {
    const el = document.getElementById(resultElementId);
    if (!el) return;

    if (!pincode || pincode.length !== 6) {
        el.innerHTML = `<span class="text-xs text-rose-600 font-medium"><i class="fa-solid fa-circle-exclamation mr-1"></i> Enter a valid 6-digit Indian PIN code</span>`;
        return;
    }

    el.innerHTML = `<span class="text-xs text-gray-500"><i class="fa-solid fa-spinner fa-spin mr-1"></i> Checking serviceability...</span>`;

    try {
        const res = await fetch(`/api/shipping/calculate?pincode=${pincode}&subtotal=${subtotal}`);
        const data = await res.json();

        if (data.serviceable) {
            const feeText = data.is_free_shipping ? '<span class="text-emerald-700 font-bold">FREE Delivery</span>' : `Delivery: <strong>${formatINR(data.shipping_fee)}</strong>`;
            el.innerHTML = `
                <div class="mt-2 p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 leading-relaxed">
                    <p class="font-semibold text-emerald-800"><i class="fa-solid fa-circle-check text-emerald-600 mr-1"></i> Delivery available to ${data.city}, ${data.state} (${data.pincode})</p>
                    <p class="mt-1">${feeText} • Estimated Delivery: <strong>${data.estimated_days}</strong> (${data.estimated_date})</p>
                </div>
            `;
        } else {
            el.innerHTML = `
                <div class="mt-2 p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800">
                    <i class="fa-solid fa-triangle-exclamation text-rose-600 mr-1"></i> ${data.message || 'PIN code is currently unserviceable.'}
                </div>
            `;
        }
    } catch (err) {
        el.innerHTML = `<span class="text-xs text-rose-600">Could not verify delivery. Please try again.</span>`;
    }
}

// ----------------- Live Predictive Search -----------------
let searchDebounceTimeout = null;
function handleLiveSearch(input) {
    clearTimeout(searchDebounceTimeout);
    const dropdown = document.getElementById('search-dropdown');
    const query = input.value.trim();

    if (query.length < 2) {
        if (dropdown) dropdown.classList.add('hidden');
        return;
    }

    searchDebounceTimeout = setTimeout(async () => {
        try {
            const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
            const results = await res.json();
            if (!dropdown) return;

            if (results.length === 0) {
                dropdown.innerHTML = `
                    <div class="p-4 text-center text-sm text-gray-500">
                        No products found matching "<strong>${query}</strong>"
                    </div>
                `;
            } else {
                dropdown.innerHTML = results.map(item => `
                    <a href="/product/${item.slug}" class="flex items-center gap-3 p-3 hover:bg-rose-50 transition border-b border-gray-100 last:border-b-0">
                        <img src="${item.primary_image || '/static/images/logo.jpg'}" alt="${item.name}" class="w-12 h-14 object-cover rounded">
                        <div class="flex-1 min-w-0">
                            <p class="text-sm font-semibold text-gray-900 truncate">${item.name}</p>
                            <p class="text-xs text-gray-500">${item.category_name}</p>
                            <p class="text-xs font-bold text-gold mt-0.5">${formatINR(item.price)}</p>
                        </div>
                    </a>
                `).join('');
            }
            dropdown.classList.remove('hidden');
        } catch (err) {
            console.error(err);
        }
    }, 250);
}

// Close search dropdown on click outside
document.addEventListener('click', (e) => {
    const searchWrapper = document.getElementById('search-wrapper');
    const dropdown = document.getElementById('search-dropdown');
    if (searchWrapper && dropdown && !searchWrapper.contains(e.target)) {
        dropdown.classList.add('hidden');
    }
});

// Mobile Navigation Toggle
function toggleMobileNav() {
    const nav = document.getElementById('mobile-nav-drawer');
    const backdrop = document.getElementById('mobile-nav-backdrop');
    if (!nav || !backdrop) return;

    const isClosed = nav.classList.contains('-translate-x-full');
    if (isClosed) {
        backdrop.classList.remove('hidden');
        requestAnimationFrame(() => {
            backdrop.classList.remove('opacity-0');
            nav.classList.remove('-translate-x-full');
        });
    } else {
        nav.classList.add('-translate-x-full');
        backdrop.classList.add('opacity-0');
        setTimeout(() => backdrop.classList.add('hidden'), 300);
    }
}

// Document Ready Initialization
document.addEventListener('DOMContentLoaded', () => {
    // Initial fetch to sync badge counts
    refreshCartDrawer();
});

// ==========================================
// SHUBHASHTU AI STYLIST & CONCIERGE AGENT
// Powered by Vercel AI SDK Tool-Calling Model
// ==========================================
let aiChatHistory = [];

function toggleAiStylist(open = null) {
    const drawer = document.getElementById('aiStylistDrawer');
    if (!drawer) return;
    const isCurrentlyActive = drawer.classList.contains('active');
    const shouldOpen = open !== null ? open : !isCurrentlyActive;

    if (shouldOpen) {
        drawer.classList.add('active');
        document.getElementById('aiChatInput')?.focus();
    } else {
        drawer.classList.remove('active');
    }
}

function handleQuickChip(btn) {
    const text = btn.textContent.trim().replace(/^[^\w\s]+/, '').trim();
    const chipsWrapper = document.getElementById('aiQuickChips');
    if (chipsWrapper) chipsWrapper.style.display = 'none';
    sendAiMessage(text);
}

function handleAiChatSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('aiChatInput');
    const text = input ? input.value.trim() : '';
    if (!text) return;
    input.value = '';
    const chipsWrapper = document.getElementById('aiQuickChips');
    if (chipsWrapper) chipsWrapper.style.display = 'none';
    sendAiMessage(text);
}

async function sendAiMessage(userText) {
    const container = document.getElementById('aiChatMessages');
    if (!container) return;

    // 1. Append User Message
    const userDiv = document.createElement('div');
    userDiv.className = 'flex items-start justify-end gap-2';
    userDiv.innerHTML = `
        <div class="bg-gray-900 text-white p-3 rounded-2xl rounded-tr-none max-w-[85%] text-xs shadow-2xs leading-relaxed">
            ${escapeHtml(userText)}
        </div>
        <div class="w-6 h-6 rounded-full bg-gray-200 flex-shrink-0 flex items-center justify-center text-gray-700 text-[10px] font-bold">
            <i class="fa-solid fa-user"></i>
        </div>
    `;
    container.appendChild(userDiv);
    container.scrollTop = container.scrollHeight;

    // 2. Append Typing Indicator
    const typingId = 'typing-' + Date.now();
    const typingDiv = document.createElement('div');
    typingDiv.id = typingId;
    typingDiv.className = 'flex items-start gap-2.5';
    typingDiv.innerHTML = `
        <div class="w-6 h-6 rounded-full bg-gold/20 border border-gold flex-shrink-0 flex items-center justify-center text-gold text-[10px]">
            <i class="fa-solid fa-wand-magic-sparkles"></i>
        </div>
        <div class="bg-white p-3 rounded-2xl rounded-tl-none border border-rose-100 shadow-2xs text-gray-500 text-[11px] flex items-center gap-2">
            <span class="inline-block w-2 h-2 rounded-full bg-gold animate-ping"></span>
            <span>AI Stylist is searching catalog & styling...</span>
        </div>
    `;
    container.appendChild(typingDiv);
    container.scrollTop = container.scrollHeight;

    aiChatHistory.push({ role: 'user', content: userText });

    try {
        const res = await fetch('/api/ai/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: userText, history: aiChatHistory })
        });
        const data = await res.json();

        // Remove typing indicator
        document.getElementById(typingId)?.remove();

        // 3. Append Assistant Response
        const asstDiv = document.createElement('div');
        asstDiv.className = 'flex items-start gap-2.5';

        // Parse markdown formatting (bold, bullets, links)
        let formattedText = escapeHtml(data.response || '')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code class="bg-gray-100 text-gray-800 px-1 py-0.5 rounded font-mono text-[10px]">$1</code>')
            .replace(/\n\n/g, '<br><br>')
            .replace(/\n/g, '<br>');

        let productsHtml = '';
        if (data.products && data.products.length > 0) {
            productsHtml = `
                <div class="mt-3 grid grid-cols-1 gap-2 pt-2 border-t border-rose-100">
                    ${data.products.map(p => `
                        <div class="bg-white p-2 rounded-xl border border-rose-200/80 shadow-2xs flex items-center justify-between gap-2.5 hover:border-gold transition">
                            <img src="${p.image || '/static/images/logo.jpg'}" alt="${escapeHtml(p.name)}" class="w-11 h-12 object-cover rounded-lg border border-gray-100 flex-shrink-0">
                            <div class="flex-1 min-w-0">
                                <a href="/product/${p.slug}" target="_blank" class="font-bold text-gray-900 text-[11px] hover:text-gold block truncate">
                                    ${escapeHtml(p.name)}
                                </a>
                                <p class="text-[10px] text-gray-500 font-semibold mt-0.5">
                                    ₹${Number(p.price).toFixed(2)}
                                    ${p.mrp > p.price ? `<span class="line-through text-gray-400 font-normal ml-1">₹${Number(p.mrp).toFixed(2)}</span>` : ''}
                                </p>
                            </div>
                            <button onclick="addToCart(${p.id}, 1, 'Free Size'); showToast('Added to bag!', 'success');" class="p-1.5 rounded-lg bg-gold text-white hover:bg-gold-dark transition text-[11px] flex-shrink-0" title="Add to Bag">
                                <i class="fa-solid fa-cart-plus"></i>
                            </button>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        let suggestionsHtml = '';
        if (data.suggestions && data.suggestions.length > 0) {
            suggestionsHtml = `
                <div class="flex flex-wrap gap-1.5 mt-2.5 pt-1">
                    ${data.suggestions.map(s => `
                        <button type="button" onclick="handleQuickChip(this)" class="px-2 py-0.5 rounded-full bg-white border border-rose-200 text-gray-700 text-[10px] font-medium hover:border-gold hover:text-gold transition shadow-2xs">
                            ${escapeHtml(s)}
                        </button>
                    `).join('')}
                </div>
            `;
        }

        asstDiv.innerHTML = `
            <div class="w-6 h-6 rounded-full bg-gold/20 border border-gold flex-shrink-0 flex items-center justify-center text-gold text-[10px]">
                <i class="fa-solid fa-wand-magic-sparkles"></i>
            </div>
            <div class="bg-white p-3.5 rounded-2xl rounded-tl-none border border-rose-100 shadow-2xs max-w-[85%] text-gray-800 leading-relaxed">
                <div>${formattedText}</div>
                ${productsHtml}
                ${suggestionsHtml}
            </div>
        `;
        container.appendChild(asstDiv);
        container.scrollTop = container.scrollHeight;

        aiChatHistory.push({ role: 'assistant', content: data.response });
    } catch (err) {
        document.getElementById(typingId)?.remove();
        showToast('AI Stylist is temporarily unavailable. Please try again.', 'error');
    }
}

function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// ----------------- Robust Clipboard Helper -----------------
function copyToClipboard(text, successMessage = 'Copied to clipboard!') {
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text)
            .then(() => showToast(successMessage, 'success'))
            .catch(() => fallbackCopy(text, successMessage));
    } else {
        fallbackCopy(text, successMessage);
    }
}

function fallbackCopy(text, successMessage) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-9999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
        document.execCommand('copy');
        showToast(successMessage, 'success');
    } catch (err) {
        showToast(text, 'info');
    }
    document.body.removeChild(textArea);
}

