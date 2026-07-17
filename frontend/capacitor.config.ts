import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "au.net.yotowebmgr.app",
  appName: "YotoWebMgr",
  webDir: "dist",
  server: {
    androidScheme: "http",
    cleartext: true,
  },
};

export default config;
