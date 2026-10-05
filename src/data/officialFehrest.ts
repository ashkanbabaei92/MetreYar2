import { parseFehrestText, mergeFehrest } from "./fehrest";
import rawFehrest1404 from "../../data/fehrest baha 1404/all 1404 fehrest.txt?raw";

/**
 * پایگاه پیش‌فرض: فهرست‌بهای واقعی ۱۴۰۴ بر پایهٔ embedded (fallback).
 *
 * فایل رسمی «all 1404 fehrest.txt» خوانده و بر روی ردیف‌های embedded مرج
 * (merge) می‌شود؛ قیمت‌های رسمی جایگزین تخمینی می‌شوند. ردیف‌های غایب در
 * فایل رسمی (مثل ۰۸۰۳۰۳) از embedded زنده می‌مانند.
 */
export function buildOfficial1404Db() {
  const { rows } = parseFehrestText(rawFehrest1404);
  return mergeFehrest(rows);
}

export const OFFICIAL_1404_FEHREST = buildOfficial1404Db();
