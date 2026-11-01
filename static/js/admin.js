"use strict";

const $ = (selector) => document.querySelector(selector);

const state = {
    orders: [],
    menu: [],
    restaurants: [],
    staff: [],
    deliveries: []
};

const sectionTitles = {
    overview: "Dashboard Overview",
    orders: "Order Management",
    menu: "Menu Management",
    staff: "Delivery Staff",
    deliveries: "Delivery Tracking"
};

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[char]);
}

function money(value) {
    return "₹" + Number(value || 0).toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function statusClass(value) {
    return "status-" + String(value || "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");
}

function badge(value) {
    return `<span class="status-badge ${statusClass(value)}">${escapeHTML(value)}</span>`;
}

function showMessage(message, type = "success") {
    const element = $("#global-message");
    element.textContent = message;
    element.className = `message ${type}`;

    window.scrollTo({ top: 0, behavior: "smooth" });

    window.setTimeout(() => {
        element.classList.add("hidden");
    }, 5000);
}

async function fetchJSON(url, options = {}) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]') ? document.querySelector('meta[name="csrf-token"]').getAttribute("content") : "";
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
            ...(options.headers || {})
        }
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(data.error || `Request failed (${response.status}).`);
    }

    return data;
}

function apiOptions(method, body) {
    return {
        method,
        body: JSON.stringify(body)
    };
}

function showSection(section) {
    if (!sectionTitles[section]) return;

    document.querySelectorAll(".page-section").forEach((element) => {
        element.classList.toggle("active", element.id === `section-${section}`);
    });

    document.querySelectorAll(".nav-link").forEach((element) => {
        element.classList.toggle("active", element.dataset.section === section);
    });

    $("#page-title").textContent = sectionTitles[section];

    if (section === "overview") loadOverview();
    if (section === "orders") loadOrders();
    if (section === "menu") loadMenu();
    if (section === "staff") loadStaff();
    if (section === "deliveries") loadDeliveries();
}

function renderOrderRows(orders, includeActions = true) {
    if (!orders.length) {
        return `<tr><td colspan="${includeActions ? 7 : 5}" class="empty-state">No orders found.</td></tr>`;
    }

    return orders.map((order) => {
        const customer = `
            <strong>${escapeHTML(order.customer_name)}</strong><br>
            <small>${escapeHTML(order.email || "")}</small>
            ${order.phone ? `<br><small>${escapeHTML(order.phone)}</small>` : ""}
        `;

        const date = order.order_date
            ? escapeHTML(order.order_date)
            : "—";

        const items = escapeHTML(order.items || "No items");

        if (!includeActions) {
            return `
                <tr>
                    <td>#${order.order_id}</td>
                    <td>${escapeHTML(order.customer_name)}</td>
                    <td>${items}</td>
                    <td>${money(order.total_amount)}</td>
                    <td>${badge(order.order_status)}</td>
                </tr>
            `;
        }

        let options = "";

        if (order.order_status === "Pending") {
            options = `
                <option value="Preparing">Preparing</option>
                <option value="Cancelled">Cancelled</option>
            `;
        } else if (order.order_status === "Preparing") {
            options = `<option value="Delivered">Delivered</option>`;
        }

        const statusControl = options
            ? `
                <select class="field-control order-status-select"
                        data-order-id="${order.order_id}">
                    <option value="">Choose status</option>
                    ${options}
                </select>
              `
            : `<span class="muted">No further changes</span>`;

        return `
            <tr>
                <td><strong>#${order.order_id}</strong></td>
                <td>${customer}</td>
                <td>${items}</td>
                <td>${money(order.total_amount)}</td>
                <td>${date}</td>
                <td>${badge(order.order_status)}</td>
                <td>${statusControl}</td>
            </tr>
        `;
    }).join("");
}

async function loadStats() {
    const stats = await fetchJSON("/api/admin/stats");

    $("#stat-total-orders").textContent = stats.total_orders ?? 0;
    $("#stat-pending-orders").textContent = stats.pending_orders ?? 0;
    $("#stat-preparing-orders").textContent = stats.preparing_orders ?? 0;
    $("#stat-delivered-orders").textContent = stats.delivered_orders ?? 0;
    $("#stat-total-sales").textContent = money(stats.total_sales);
}

async function loadOrders() {
    try {
        state.orders = await fetchJSON("/api/admin/orders");

        renderOrdersTable();
        renderRecentOrders();
        populateAssignmentOrders();
    } catch (error) {
        showMessage(error.message, "error");
        $("#orders-body").innerHTML =
            `<tr><td colspan="7" class="empty-state">Could not load orders.</td></tr>`;
    }
}

function renderOrdersTable() {
    const filter = $("#order-filter").value;

    const filtered = state.orders.filter((order) =>
        filter === "All" || order.order_status === filter
    );

    $("#orders-body").innerHTML = renderOrderRows(filtered, true);
}

function renderRecentOrders() {
    $("#recent-orders-body").innerHTML =
        renderOrderRows(state.orders.slice(0, 5), false);
}

async function loadOverview() {
    try {
        await Promise.all([loadStats(), loadOrders()]);
    } catch (error) {
        showMessage(error.message, "error");
    }
}

async function updateOrderStatus(orderId, newStatus, selectElement) {
    if (!newStatus) return;

    const confirmed = window.confirm(
        `Update order #${orderId} to "${newStatus}"?`
    );

    if (!confirmed) {
        selectElement.value = "";
        return;
    }

    selectElement.disabled = true;

    try {
        const result = await fetchJSON(
            `/api/admin/orders/${orderId}/status`,
            apiOptions("PATCH", { order_status: newStatus })
        );

        showMessage(result.message || "Order updated.");
        await Promise.all([loadStats(), loadOrders(), loadDeliveries()]);
    } catch (error) {
        showMessage(error.message, "error");
        selectElement.value = "";
    } finally {
        selectElement.disabled = false;
    }
}

// ============================================================
// MENU MANAGEMENT
// ============================================================

async function loadRestaurants() {
    try {
        state.restaurants = await fetchJSON("/api/admin/restaurants");

        const select = $("#menu-restaurant");
        const previousValue = select.value;

        select.innerHTML = `
            <option value="">Select restaurant</option>
            ${state.restaurants.map((restaurant) => `
                <option value="${restaurant.restaurant_id}">
                    ${escapeHTML(restaurant.name)}
                </option>
            `).join("")}
        `;

        if (previousValue) select.value = previousValue;
    } catch (error) {
        $("#menu-restaurant").innerHTML =
            `<option value="">Unable to load restaurants</option>`;
        showMessage(error.message, "error");
    }
}

async function loadMenu() {
    try {
        const results = await Promise.all([
            fetchJSON("/api/admin/menu"),
            fetchJSON("/api/admin/restaurants")
        ]);

        state.menu = results[0];
        state.restaurants = results[1];

        renderMenu();
        renderRestaurantOptions();
    } catch (error) {
        showMessage(error.message, "error");
        $("#menu-body").innerHTML =
            `<tr><td colspan="6" class="empty-state">Could not load menu items.</td></tr>`;
    }
}

function renderRestaurantOptions() {
    const select = $("#menu-restaurant");
    const previousValue = select.value;

    select.innerHTML = `
        <option value="">Select restaurant</option>
        ${state.restaurants.map((restaurant) => `
            <option value="${restaurant.restaurant_id}">
                ${escapeHTML(restaurant.name)}
            </option>
        `).join("")}
    `;

    if (previousValue) select.value = previousValue;
}

function renderMenu() {
    const search = $("#menu-search").value.trim().toLowerCase();
    const filter = $("#menu-availability-filter").value;

    const filtered = state.menu.filter((item) => {
        const text = [
            item.item_name,
            item.category,
            item.restaurant
        ].join(" ").toLowerCase();

        const matchesSearch = text.includes(search);
        const matchesAvailability =
            filter === "All" ||
            (filter === "Available" && item.available) ||
            (filter === "Unavailable" && !item.available);

        return matchesSearch && matchesAvailability;
    });

    $("#menu-item-count").textContent = state.menu.length;

    if (!filtered.length) {
        $("#menu-body").innerHTML =
            `<tr><td colspan="6" class="empty-state">No matching food items found.</td></tr>`;
        return;
    }

    $("#menu-body").innerHTML = filtered.map((item) => `
        <tr>
            <td><strong>${escapeHTML(item.item_name)}</strong></td>
            <td>${escapeHTML(item.restaurant)}</td>
            <td>${escapeHTML(item.category || "—")}</td>
            <td>${money(item.price)}</td>
            <td>${badge(item.available ? "Available" : "Unavailable")}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn btn-secondary"
                            data-menu-action="edit"
                            data-item-id="${item.item_id}">
                        Edit
                    </button>
                    <button class="btn ${item.available ? "btn-danger" : "btn-success"}"
                            data-menu-action="toggle"
                            data-item-id="${item.item_id}">
                        ${item.available ? "Disable" : "Enable"}
                    </button>
                    <button class="btn btn-danger"
                            data-menu-action="delete"
                            data-item-id="${item.item_id}">
                        Remove
                    </button>
                </div>
            </td>
        </tr>
    `).join("");
}

function resetMenuForm() {
    $("#menu-form").reset();
    $("#menu-item-id").value = "";
    $("#menu-available").checked = true;
    $("#menu-form-title").textContent = "Add a Food Item";
    $("#menu-submit-btn").textContent = "+ Add Food Item";
    $("#menu-reset-btn").classList.add("hidden");
}

function editMenuItem(itemId) {
    const item = state.menu.find((entry) => entry.item_id === itemId);

    if (!item) {
        showMessage("Food item not found.", "error");
        return;
    }

    $("#menu-item-id").value = item.item_id;
    $("#menu-item-name").value = item.item_name;
    $("#menu-category").value = item.category || "";
    $("#menu-price").value = item.price;
    $("#menu-restaurant").value = item.restaurant_id;
    $("#menu-available").checked = Boolean(item.available);

    $("#menu-form-title").textContent = `Edit Food Item #${item.item_id}`;
    $("#menu-submit-btn").textContent = "Save Changes";
    $("#menu-reset-btn").classList.remove("hidden");

    $("#menu-form").scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

    $("#menu-item-name").focus();
}

async function submitMenuForm(event) {
    event.preventDefault();

    const itemId = $("#menu-item-id").value;

    const payload = {
        item_name: $("#menu-item-name").value.trim(),
        category: $("#menu-category").value.trim(),
        price: Number($("#menu-price").value),
        restaurant_id: Number($("#menu-restaurant").value),
        available: $("#menu-available").checked
    };

    if (
        !payload.item_name ||
        !payload.restaurant_id ||
        !Number.isFinite(payload.price) ||
        payload.price <= 0
    ) {
        showMessage("Enter a food name, restaurant, and valid price.", "error");
        return;
    }

    const submitButton = $("#menu-submit-btn");
    submitButton.disabled = true;

    try {
        let result;

        if (itemId) {
            result = await fetchJSON(
                `/api/admin/menu/${itemId}`,
                apiOptions("PATCH", payload)
            );
        } else {
            result = await fetchJSON(
                "/api/admin/menu",
                apiOptions("POST", payload)
            );
        }

        resetMenuForm();
        await loadMenu();
        showMessage(result.message || "Menu saved successfully.");
    } catch (error) {
        showMessage(error.message, "error");
    } finally {
        submitButton.disabled = false;
    }
}

async function toggleMenuAvailability(itemId) {
    const item = state.menu.find((entry) => entry.item_id === itemId);
    if (!item) return;

    const newAvailability = !item.available;
    const action = newAvailability ? "enable" : "disable";

    if (!window.confirm(
        `${action.charAt(0).toUpperCase() + action.slice(1)} "${item.item_name}"?`
    )) {
        return;
    }

    try {
        const result = await fetchJSON(
            `/api/admin/menu/${itemId}`,
            apiOptions("PATCH", { available: newAvailability })
        );

        await loadMenu();
        showMessage(result.message || "Availability updated.");
    } catch (error) {
        showMessage(error.message, "error");
    }
}

async function removeMenuItem(itemId) {
    const item = state.menu.find((entry) => entry.item_id === itemId);
    if (!item) return;

    const confirmed = window.confirm(
        `Remove "${item.item_name}" from the customer menu?\n\n` +
        "It will be marked unavailable, preserving historical orders."
    );

    if (!confirmed) return;

    try {
        const result = await fetchJSON(
            `/api/admin/menu/${itemId}`,
            { method: "DELETE" }
        );

        if ($("#menu-item-id").value === String(itemId)) {
            resetMenuForm();
        }

        await loadMenu();
        showMessage(result.message || "Food item removed.");
    } catch (error) {
        showMessage(error.message, "error");
    }
}

// ============================================================
// DELIVERY STAFF
// ============================================================

async function loadStaff() {
    try {
        state.staff = await fetchJSON("/api/admin/delivery-persons");
        renderStaff();
        populateAssignmentStaff();
    } catch (error) {
        showMessage(error.message, "error");
        $("#staff-list").innerHTML =
            `<p class="empty-state">Could not load delivery staff.</p>`;
    }
}

function renderStaff() {
    if (!state.staff.length) {
        $("#staff-list").innerHTML =
            `<p class="empty-state">No delivery staff registered yet.</p>`;
        return;
    }

    $("#staff-list").innerHTML = state.staff.map((person) => `
        <article class="staff-card">
            <h3>${escapeHTML(person.name)}</h3>
            <p>☎ ${escapeHTML(person.phone)}</p>
            <p>ID: #${person.delivery_person_id}</p>
            ${badge(person.is_available ? "Available" : "Unavailable")}
        </article>
    `).join("");
}

async function submitStaffForm(event) {
    event.preventDefault();

    const name = $("#staff-name").value.trim();
    const phone = $("#staff-phone").value.trim();

    if (!name || !phone) {
        showMessage("Enter the delivery person's name and phone.", "error");
        return;
    }

    try {
        const result = await fetchJSON(
            "/api/admin/delivery-persons",
            apiOptions("POST", { name, phone })
        );

        $("#staff-form").reset();
        await loadStaff();
        showMessage(result.message || "Delivery staff added.");
    } catch (error) {
        showMessage(error.message, "error");
    }
}

// ============================================================
// DELIVERY ASSIGNMENT AND TRACKING
// ============================================================

function populateAssignmentOrders() {
    const select = $("#assign-order");
    const previousValue = select.value;

    const eligible = state.orders.filter((order) =>
        ["Pending", "Preparing"].includes(order.order_status)
    );

    select.innerHTML = `
        <option value="">Select order</option>
        ${eligible.map((order) => `
            <option value="${order.order_id}">
                #${order.order_id} — ${escapeHTML(order.customer_name)}
                — ${money(order.total_amount)}
            </option>
        `).join("")}
    `;

    if (previousValue) select.value = previousValue;
}

function populateAssignmentStaff() {
    const select = $("#assign-staff");
    const previousValue = select.value;

    const available = state.staff.filter((person) => person.is_available);

    select.innerHTML = `
        <option value="">Select available staff</option>
        ${available.map((person) => `
            <option value="${person.delivery_person_id}">
                ${escapeHTML(person.name)} — ${escapeHTML(person.phone)}
            </option>
        `).join("")}
    `;

    if (previousValue) select.value = previousValue;
}

async function submitAssignment(event) {
    event.preventDefault();

    const payload = {
        order_id: Number($("#assign-order").value),
        delivery_person_id: Number($("#assign-staff").value),
        delivery_address: $("#delivery-address").value.trim(),
        building_details: $("#building-details").value.trim()
    };

    if (!payload.order_id || !payload.delivery_person_id) {
        showMessage("Choose an order and available delivery person.", "error");
        return;
    }

    try {
        const result = await fetchJSON(
            "/api/admin/deliveries/assign",
            apiOptions("POST", payload)
        );

        $("#assign-form").reset();

        await Promise.all([loadOrders(), loadStaff(), loadDeliveries()]);
        showMessage(result.message || "Delivery assigned successfully.");
    } catch (error) {
        showMessage(error.message, "error");
    }
}

async function loadDeliveries() {
    try {
        state.deliveries = await fetchJSON("/api/admin/deliveries");
        renderDeliveries();
    } catch (error) {
        showMessage(error.message, "error");
        $("#deliveries-body").innerHTML =
            `<tr><td colspan="6" class="empty-state">Could not load deliveries.</td></tr>`;
    }
}

function renderDeliveries() {
    if (!state.deliveries.length) {
        $("#deliveries-body").innerHTML =
            `<tr><td colspan="6" class="empty-state">No deliveries to display.</td></tr>`;
        return;
    }

    $("#deliveries-body").innerHTML = state.deliveries.map((delivery) => {
        const address = [
            delivery.delivery_address,
            delivery.building_details
        ].filter(Boolean).join(", ");

        let options = "";

        if (delivery.delivery_status === "Assigned") {
            options = `
                <option value="Picked Up">Picked Up</option>
                <option value="Cancelled">Cancelled</option>
            `;
        } else if (delivery.delivery_status === "Picked Up") {
            options = `
                <option value="Out for Delivery">Out for Delivery</option>
                <option value="Cancelled">Cancelled</option>
            `;
        } else if (delivery.delivery_status === "Out for Delivery") {
            options = `
                <option value="Delivered">Delivered</option>
                <option value="Cancelled">Cancelled</option>
            `;
        }

        const updateControl = options
            ? `
                <select class="field-control delivery-status-select"
                        data-delivery-id="${delivery.delivery_id}">
                    <option value="">Update status</option>
                    ${options}
                </select>
            `
            : `<span class="muted">No further changes</span>`;

        return `
            <tr>
                <td>
                    <strong>#${delivery.delivery_id}</strong><br>
                    <small>Order #${delivery.order_id}</small>
                </td>
                <td>
                    ${escapeHTML(delivery.customer_name || "—")}<br>
                    <small>${escapeHTML(delivery.customer_phone || "")}</small>
                </td>
                <td>${escapeHTML(address || "Address not provided")}</td>
                <td>
                    ${escapeHTML(delivery.delivery_person_name || "Not assigned")}<br>
                    <small>${escapeHTML(delivery.delivery_person_phone || "")}</small>
                </td>
                <td>${badge(delivery.delivery_status)}</td>
                <td>${updateControl}</td>
            </tr>
        `;
    }).join("");
}

async function updateDeliveryStatus(deliveryId, newStatus, selectElement) {
    if (!newStatus) return;

    if (!window.confirm(
        `Update delivery #${deliveryId} to "${newStatus}"?`
    )) {
        selectElement.value = "";
        return;
    }

    selectElement.disabled = true;

    try {
        const result = await fetchJSON(
            `/api/admin/deliveries/${deliveryId}/status`,
            apiOptions("PATCH", { delivery_status: newStatus })
        );

        await Promise.all([
            loadDeliveries(),
            loadOrders(),
            loadStats(),
            loadStaff()
        ]);

        showMessage(result.message || "Delivery status updated.");
    } catch (error) {
        showMessage(error.message, "error");
        selectElement.value = "";
    } finally {
        selectElement.disabled = false;
    }
}

// ============================================================
// EVENTS
// ============================================================

document.querySelectorAll(".nav-link").forEach((button) => {
    button.addEventListener("click", () => {
        showSection(button.dataset.section);
    });
});

document.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => {
        showSection(button.dataset.go);
    });
});

$("#refresh-all").addEventListener("click", async () => {
    try {
        await Promise.all([
            loadStats(),
            loadOrders(),
            loadMenu(),
            loadStaff(),
            loadDeliveries()
        ]);
        showMessage("Dashboard data refreshed.");
    } catch (error) {
        showMessage(error.message, "error");
    }
});

$("#order-filter").addEventListener("change", renderOrdersTable);

$("#orders-body").addEventListener("change", (event) => {
    const select = event.target.closest(".order-status-select");
    if (!select) return;

    updateOrderStatus(
        Number(select.dataset.orderId),
        select.value,
        select
    );
});

$("#menu-form").addEventListener("submit", submitMenuForm);
$("#menu-reset-btn").addEventListener("click", resetMenuForm);
$("#refresh-menu").addEventListener("click", loadMenu);
$("#menu-search").addEventListener("input", renderMenu);
$("#menu-availability-filter").addEventListener("change", renderMenu);

$("#menu-body").addEventListener("click", (event) => {
    const button = event.target.closest("[data-menu-action]");
    if (!button) return;

    const itemId = Number(button.dataset.itemId);

    if (button.dataset.menuAction === "edit") {
        editMenuItem(itemId);
    } else if (button.dataset.menuAction === "toggle") {
        toggleMenuAvailability(itemId);
    } else if (button.dataset.menuAction === "delete") {
        removeMenuItem(itemId);
    }
});

$("#staff-form").addEventListener("submit", submitStaffForm);
$("#assign-form").addEventListener("submit", submitAssignment);
$("#refresh-deliveries").addEventListener("click", loadDeliveries);

$("#deliveries-body").addEventListener("change", (event) => {
    const select = event.target.closest(".delivery-status-select");
    if (!select) return;

    updateDeliveryStatus(
        Number(select.dataset.deliveryId),
        select.value,
        select
    );
});

// ============================================================
// INITIAL LOAD
// ============================================================

async function initializeDashboard() {
    try {
        await Promise.all([
            loadStats(),
            loadOrders(),
            loadMenu(),
            loadStaff(),
            loadDeliveries()
        ]);
    } catch (error) {
        showMessage(error.message, "error");
    }
}

initializeDashboard();