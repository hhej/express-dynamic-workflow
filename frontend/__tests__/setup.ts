import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { server } from './mocks/server';

/**
 * Node 25 ships an experimental `globalThis.localStorage` that is enabled
 * by default but has no usable methods unless `--localstorage-file` is set.
 * vitest's jsdom populator skips copying `dom.window.localStorage` onto
 * global because the (broken) Node global already exists, so tests see an
 * empty object lacking `clear/getItem/setItem/removeItem`.
 *
 * Install a minimal Map-backed Storage polyfill — sufficient for our tests
 * which only exercise getItem/setItem/removeItem/clear under
 * LOCAL_STORAGE_KEYS.threadId. Replace both `globalThis.localStorage` and
 * `window.localStorage` so all access paths agree.
 */
function installStoragePolyfill() {
  function createStorage(): Storage {
    const store = new Map<string, string>();
    return {
      get length() {
        return store.size;
      },
      clear() {
        store.clear();
      },
      getItem(key: string) {
        return store.has(key) ? (store.get(key) as string) : null;
      },
      key(index: number) {
        return Array.from(store.keys())[index] ?? null;
      },
      removeItem(key: string) {
        store.delete(key);
      },
      setItem(key: string, value: string) {
        store.set(key, String(value));
      },
    };
  }
  Object.defineProperty(globalThis, 'localStorage', {
    value: createStorage(),
    writable: true,
    configurable: true,
  });
  Object.defineProperty(globalThis, 'sessionStorage', {
    value: createStorage(),
    writable: true,
    configurable: true,
  });
  if (typeof window !== 'undefined') {
    Object.defineProperty(window, 'localStorage', {
      value: globalThis.localStorage,
      writable: true,
      configurable: true,
    });
    Object.defineProperty(window, 'sessionStorage', {
      value: globalThis.sessionStorage,
      writable: true,
      configurable: true,
    });
  }
}

installStoragePolyfill();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
