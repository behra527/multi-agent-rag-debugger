export function loadOrder() {
  return Promise.resolve({
    items: [
      { sku: "A", price: 10 },
      { sku: "B", price: 5 },
    ],
  });
}

export function orderTotal() {
  const order = loadOrder();
  return order.items.reduce((sum, item) => sum + item.price, 0);
}
