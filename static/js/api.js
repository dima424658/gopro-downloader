export async function requestJson(url, { method = "GET", data, fallback = "Request failed.", signal } = {}) {
  const options = { method, signal, headers: {} };
  if (data !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(data);
  }

  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.error || fallback);
  }
  return result;
}
