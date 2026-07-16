/// <reference types="vite/client" />

declare global {
  interface Window {
    NDEFReader: {
      new (): {
        scan: () => Promise<void>;
        onreading: ((event: Event) => void) | null;
        onerror: (() => void) | null;
      };
    };
  }
}

export {};
