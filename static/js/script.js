
let foodMenu = [];
let cart = [];
let isPlacingOrder = false;

function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
}

// ---- Category emoji helper ----
function categoryEmoji(category) {
    if (!category) return "🍽️";
    const c = category.toLowerCase();
    if (c.includes("pizza")) return "🍕";
    if (c.includes("burger")) return "🍔";
    if (c.includes("biryani") || c.includes("rice")) return "🍚";
    if (c.includes("chicken") || c.includes("non-veg") || c.includes("meat")) return "🍗";
    if (c.includes("dessert") || c.includes("sweet") || c.includes("cake")) return "🍰";
    if (c.includes("drink") || c.includes("beverage") || c.includes("juice")) return "🥤";
    if (c.includes("noodle") || c.includes("pasta")) return "🍜";
    if (c.includes("salad") || c.includes("veg")) return "🥗";
    if (c.includes("sandwich") || c.includes("sub")) return "🥪";
    if (c.includes("roll") || c.includes("wrap")) return "🌯";
    if (c.includes("soup")) return "🍲";
    return "🍽️";
}

async function loadMenu() {
    const container = document.getElementById("food-menu");
    container.textContent = "Loading food menu...";

    try {
        const response = await fetch("/api/menu");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Failed to load menu.");
        }

        foodMenu = data;
        container.innerHTML = "";

        if (!foodMenu.length) {
            container.textContent = "No food items available.";
            return;
        }

        // Populate category filter
        const categoryFilter = document.getElementById("category-filter");
        const categories = [...new Set(foodMenu.map(f => f.category).filter(Boolean))].sort();
        categories.forEach(cat => {
            const opt = document.createElement("option");
            opt.value = cat;
            opt.textContent = cat;
            categoryFilter.appendChild(opt);
        });

        foodMenu.forEach(food => {
            const card = document.createElement("article");
            card.className = "food-card";
            card.dataset.name = (food.item_name || "").toLowerCase();
            card.dataset.restaurant = (food.restaurant || "").toLowerCase();
            card.dataset.category = (food.category || "").toLowerCase();

            const iconArea = document.createElement("div");
            iconArea.className = "food-card-icon";
            iconArea.textContent = categoryEmoji(food.category);

            const body = document.createElement("div");
            body.className = "food-card-body";

            const name = document.createElement("h3");
            name.textContent = food.item_name;

            const restaurant = document.createElement("p");
            restaurant.className = "restaurant";
            restaurant.textContent = "🏪 " + food.restaurant;

            const category = document.createElement("p");
            category.className = "category";
            category.textContent = food.category || "Other";

            const price = document.createElement("p");
            price.className = "price";
            price.textContent = `₹${Number(food.price).toFixed(2)}`;

            const button = document.createElement("button");
            button.type = "button";
            button.textContent = "Add to Cart";
            button.addEventListener("click", () => addToCart(food.item_id));

            body.append(name, restaurant, category, price, button);
            card.append(iconArea, body);
            container.appendChild(card);
        });

        // Wire up search & filter after cards are rendered
        wireMenuSearch();

    } catch (error) {
        console.error(error);
        container.textContent = "Unable to load the food menu.";
    }
}

// ---- Search & Filter Logic ----
function wireMenuSearch() {
    const searchInput = document.getElementById("menu-search");
    const categoryFilter = document.getElementById("category-filter");

    function filterCards() {
        const query = (searchInput ? searchInput.value : "").toLowerCase().trim();
        const selectedCat = (categoryFilter ? categoryFilter.value : "").toLowerCase().trim();
        const cards = document.querySelectorAll("#food-menu .food-card");

        cards.forEach(card => {
            const nameMatch  = card.dataset.name.includes(query);
            const restMatch  = card.dataset.restaurant.includes(query);
            const catSearch  = card.dataset.category.includes(query);
            const textMatch  = !query || nameMatch || restMatch || catSearch;
            const catMatch   = !selectedCat || card.dataset.category === selectedCat;
            card.style.display = (textMatch && catMatch) ? "" : "none";
        });
    }

    if (searchInput)  searchInput.addEventListener("input",  filterCards);
    if (categoryFilter) categoryFilter.addEventListener("change", filterCards);
}

function addToCart(itemId) {
    const food = foodMenu.find(
        item => Number(item.item_id) === Number(itemId)
    );
    if (!food) return;

    const existing = cart.find(
        item => Number(item.item_id) === Number(itemId)
    );

    if (existing) {
        existing.quantity += 1;
    } else {
        cart.push({ ...food, quantity: 1 });
    }

    renderCart();
}

function changeQuantity(itemId, change) {
    const item = cart.find(
        food => Number(food.item_id) === Number(itemId)
    );
    if (!item) return;

    item.quantity += change;

    if (item.quantity <= 0) {
        cart = cart.filter(
            food => Number(food.item_id) !== Number(itemId)
        );
    }

    renderCart();
}

function removeFromCart(itemId) {
    cart = cart.filter(
        food => Number(food.item_id) !== Number(itemId)
    );
    renderCart();
}

function clearCart() {
    cart = [];
    renderCart();
}

function renderCart() {
    const container = document.getElementById("cart-items");
    const totalElement = document.getElementById("cart-total");

    container.innerHTML = "";

    if (!cart.length) {
        container.textContent = "Your cart is empty.";
        totalElement.textContent = "0.00";
        return;
    }

    let total = 0;

    cart.forEach(item => {
        const price = Number(item.price);
        const subtotal = price * item.quantity;
        total += subtotal;

        const row = document.createElement("div");
        row.className = "cart-item";

        const info = document.createElement("div");
        info.className = "cart-item-info";

        const name = document.createElement("strong");
        name.textContent = item.item_name;

        const details = document.createElement("p");
        details.textContent = `₹${price.toFixed(2)} each`;

        const subtotalText = document.createElement("p");
        subtotalText.textContent = `Subtotal: ₹${subtotal.toFixed(2)}`;

        info.append(name, details, subtotalText);

        const controls = document.createElement("div");
        controls.className = "quantity-controls";

        const decrease = document.createElement("button");
        decrease.type = "button";
        decrease.textContent = "−";
        decrease.setAttribute("aria-label", "Decrease quantity");
        decrease.addEventListener(
            "click", () => changeQuantity(item.item_id, -1)
        );

        const quantity = document.createElement("span");
        quantity.textContent = item.quantity;

        const increase = document.createElement("button");
        increase.type = "button";
        increase.textContent = "+";
        increase.setAttribute("aria-label", "Increase quantity");
        increase.addEventListener(
            "click", () => changeQuantity(item.item_id, 1)
        );

        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "remove-button";
        remove.textContent = "Remove";
        remove.addEventListener(
            "click", () => removeFromCart(item.item_id)
        );

        controls.append(decrease, quantity, increase, remove);
        row.append(info, controls);
        container.appendChild(row);
    });

    totalElement.textContent = total.toFixed(2);
}

async function placeOrder(event) {
    event.preventDefault();
    if (isPlacingOrder) return;

    const message = document.getElementById("order-message");
    const button = document.getElementById("place-order");
    const form = document.getElementById("order-form");

    if (!cart.length) {
        message.textContent = "Please add food to your cart first.";
        return;
    }

    if (!form.reportValidity()) return;

    const orderData = {
        name: document.getElementById("customer-name").value.trim(),
        email: document.getElementById("customer-email").value.trim(),
        phone: document.getElementById("customer-phone").value.trim(),
        delivery_address: document.getElementById("delivery-address").value.trim(),
        building_details: document.getElementById("building-details").value.trim(),
        items: cart.map(item => ({
            item_id: item.item_id,
            quantity: item.quantity
        }))
    };

    isPlacingOrder = true;
    button.disabled = true;
    button.textContent = "Placing Order...";
    message.textContent = "Please wait...";

    try {
        const response = await fetch("/api/orders", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken()
            },
            body: JSON.stringify(orderData)
        });

        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || "Unable to place order.");
        }

        message.textContent =
            `Order placed! Order ID: ${result.order_id}. ` +
            `Total: ₹${Number(result.total_amount).toFixed(2)}.`;

        cart = [];
        renderCart();
        form.reset();
        await loadOrderHistory();
    } catch (error) {
        console.error(error);
        message.textContent = error.message;
    } finally {
        isPlacingOrder = false;
        button.disabled = false;
        button.textContent = "Place Order";
    }
}

async function cancelOrder(orderId, button) {
    const confirmed = window.confirm(
        `Are you sure you want to cancel order #${orderId}?`
    );
    if (!confirmed) return;

    button.disabled = true;
    button.textContent = "Cancelling...";

    try {
        const response = await fetch(`/api/orders/${orderId}/cancel`, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCsrfToken()
            }
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Unable to cancel order.");
        }

        window.alert(result.message);
        await loadOrderHistory();
    } catch (error) {
        window.alert(error.message);
        await loadOrderHistory();
    }
}

async function loadOrderHistory() {
    const container = document.getElementById("order-history-list");
    container.textContent = "Loading order history...";

    try {
        const response = await fetch("/api/orders");
        const orders = await response.json();

        if (!response.ok) {
            throw new Error(orders.error || "Unable to load order history.");
        }

        container.innerHTML = "";

        if (!orders.length) {
            const empty = document.createElement("p");
            empty.className = "empty-history";
            empty.textContent = "No orders have been placed yet.";
            container.appendChild(empty);
            return;
        }

        orders.forEach(order => {
            const card = document.createElement("article");
            card.className = "order-card";

            const header = document.createElement("div");
            header.className = "order-card-header";

            const details = document.createElement("div");

            const title = document.createElement("h3");
            title.textContent = `Order #${order.order_id}`;

            const customer = document.createElement("p");
            customer.className = "order-meta";
            customer.textContent = `${order.customer_name} · ${order.email}`;

            const date = document.createElement("p");
            date.className = "order-meta";
            date.textContent = order.order_date;

            details.append(title, customer, date);

            const statusClass = `status-${order.order_status.toLowerCase()}`;
            const status = document.createElement("span");
            status.className = `order-status ${statusClass}`;
            if (order.order_status === "Cancelled") status.classList.add("cancelled");
            status.textContent = order.order_status;

            header.append(details, status);
            card.appendChild(header);

            const itemsList = document.createElement("ul");
            itemsList.className = "order-items-list";

            order.items.forEach(item => {
                const li = document.createElement("li");

                const itemName = document.createElement("span");
                itemName.textContent = `${item.item_name} × ${item.quantity}`;

                const itemPrice = document.createElement("span");
                itemPrice.textContent =
                    `₹${(Number(item.unit_price) * item.quantity).toFixed(2)}`;

                li.append(itemName, itemPrice);
                itemsList.appendChild(li);
            });

            card.appendChild(itemsList);

            const total = document.createElement("p");
            total.className = "order-total";
            total.textContent =
                `Order Total: ₹${Number(order.total_amount).toFixed(2)}`;
            card.appendChild(total);

            if (order.order_status === "Pending") {
                const cancelButton = document.createElement("button");
                cancelButton.type = "button";
                cancelButton.className = "cancel-order-button";
                cancelButton.textContent = "Cancel Order";
                cancelButton.addEventListener("click", () => {
                    cancelOrder(order.order_id, cancelButton);
                });
                card.appendChild(cancelButton);
            }

            container.appendChild(card);
        });
    } catch (error) {
        console.error(error);
        container.textContent = "Unable to load order history. Please refresh.";
    }
}

document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("clear-cart").addEventListener("click", clearCart);
    document.getElementById("order-form").addEventListener("submit", placeOrder);
    document.getElementById("refresh-orders").addEventListener(
        "click", loadOrderHistory
    );

    renderCart();
    loadMenu();
    loadOrderHistory();
});
