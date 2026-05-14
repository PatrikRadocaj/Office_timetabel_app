export function showAlert(containerId, message, type = "success") {
  const target = document.getElementById(containerId);
  if (!target) {
    return;
  }

  target.innerHTML = `
    <div class="alert alert-${type} alert-dismissible fade show" role="alert">
      ${message}
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>
  `;
}

export function clearAlert(containerId) {
  const target = document.getElementById(containerId);
  if (target) {
    target.innerHTML = "";
  }
}

export function requireValue(value, fieldName) {
  if (!String(value || "").trim()) {
    throw new Error(`${fieldName} is required`);
  }
}

export function toIsoFromLocal(value) {
  if (!value) {
    throw new Error("Datetime is required");
  }
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) {
    throw new Error("Invalid datetime format");
  }
  return dt.toISOString();
}

export function formatDateTime(value) {
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) {
    return String(value);
  }
  return dt.toLocaleString();
}
