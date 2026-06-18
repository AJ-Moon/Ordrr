class HttpError extends Error {
  status: number;

  constructor(status: number) {
    super(`HTTP ${status}`);
    this.status = status;
  }
}

function emitServiceUnavailable() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("api:service-unavailable"));
  }
}

function emitServiceRecovered() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("api:service-recovered"));
  }
}

export async function fetchJsonWithRetry<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
  options?: { retries?: number; timeoutMs?: number; backoffMs?: number },
): Promise<T> {
  const retries = options?.retries ?? 2;
  const timeoutMs = options?.timeoutMs ?? 7000;
  const backoffMs = options?.backoffMs ?? 300;

  let lastError: unknown;

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(input, {
        ...init,
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new HttpError(response.status);
      }

      emitServiceRecovered();
      return (await response.json()) as T;
    } catch (error) {
      lastError = error;

      if (error instanceof HttpError && error.status === 503) {
        emitServiceUnavailable();
      }

      if (attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, backoffMs * (attempt + 1)));
        continue;
      }
      throw lastError;
    } finally {
      clearTimeout(timeout);
    }
  }

  throw lastError ?? new Error("Request failed");
}
