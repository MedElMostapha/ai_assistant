let token = sessionStorage.getItem("amanah_token") || "";
export function setToken(value: string) {
  token = value;
  value
    ? sessionStorage.setItem("amanah_token", value)
    : sessionStorage.removeItem("amanah_token");
}
export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
  ) {
    super(code);
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const form = data instanceof FormData;
  const response = await fetch("/api" + path, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(!form && data !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
    },
    body: data === undefined ? undefined : form ? data : JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ error: "server_error" }));
    throw new ApiError(error.error || "server_error", response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
export async function downloadPdf(id: string) {
  const response = await fetch(`/api/analyses/${id}/pdf`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new ApiError("export_failed", response.status);
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = "avis-juridique.pdf";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
