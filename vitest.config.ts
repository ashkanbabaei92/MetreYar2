import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/char_ts/test_*.ts"],
    setupFiles: ["tests/char_ts/setup.ts"],
    globals: true,
    // تست‌های موتور روی دادهٔ واقعی هرکدام چند ثانیه‌ای طول می‌کشند؛ زیر
    // بارِ همزمانِ vitest از ۵ ثانیهٔ پیش‌فرض عبور می‌کردند (T09 multifile).
    testTimeout: 60_000,
  },
});
