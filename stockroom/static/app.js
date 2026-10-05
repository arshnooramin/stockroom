// Ask before submitting forms marked with data-confirm (deletes, removals).
document.addEventListener("submit", (event) => {
  const message = event.target.dataset.confirm;
  if (message && !window.confirm(message)) event.preventDefault();
});

// Flash messages render as toasts.
document.querySelectorAll(".toast").forEach((el) => bootstrap.Toast.getOrCreateInstance(el).show());

// Buttons with data-project preselect that project in the "Add project manager" modal.
document.getElementById("new-pm-modal")?.addEventListener("show.bs.modal", (event) => {
  const project = event.relatedTarget?.dataset.project;
  if (project) document.getElementById("pm-project").value = project;
});

// A checkbox with data-toggles="<selector>" disables that fieldset while checked.
document.querySelectorAll("[data-toggles]").forEach((checkbox) => {
  const target = document.querySelector(checkbox.dataset.toggles);
  const sync = () => { target.disabled = checkbox.checked; };
  checkbox.addEventListener("change", sync);
  sync();
});

// New order form: "Other" vendor fields, item rows, and running totals.
const orderForm = document.getElementById("order-form");
if (orderForm) {
  const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
  const vendor = document.getElementById("vendor");
  const vendorOther = document.getElementById("vendor-other");
  const items = document.getElementById("items");
  const template = document.getElementById("item-template");

  const syncVendor = () => {
    const isOther = vendor.value === vendor.dataset.other;
    vendorOther.hidden = !isOther;
    vendorOther.disabled = !isOther;
  };

  const syncItems = () => {
    const rows = items.querySelectorAll(".item-row");
    let subtotal = 0;
    rows.forEach((row, i) => {
      const line = (parseFloat(row.querySelector(".item-price").value) || 0) *
                   (parseInt(row.querySelector(".item-qty").value, 10) || 0);
      subtotal += line;
      row.querySelector(".item-title").textContent = `Item ${i + 1}`;
      row.querySelector(".item-number").textContent = i + 1;
      row.querySelector(".item-total").textContent = money.format(line);
      row.querySelector(".item-remove").hidden = rows.length === 1;
    });
    document.getElementById("order-subtotal").textContent = money.format(subtotal);
  };

  vendor.addEventListener("change", syncVendor);
  items.addEventListener("input", syncItems);
  items.addEventListener("click", (event) => {
    const remove = event.target.closest(".item-remove");
    if (remove) {
      remove.closest(".item-row").remove();
      syncItems();
    }
  });
  document.getElementById("add-item").addEventListener("click", () => {
    items.append(template.content.cloneNode(true));
    syncItems();
    items.lastElementChild.querySelector("input").focus();
  });

  syncVendor();
  syncItems();
}
