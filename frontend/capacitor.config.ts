import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "au.net.yotowebmgr.app",
  appName: "YotoWebMgr",
  webDir: "dist",
  plugins: {
    CapacitorUpdater: {
      autoUpdate: false,
    },
  },
  server: {
    androidScheme: "http",
    cleartext: true,
  },
};

export default config;
