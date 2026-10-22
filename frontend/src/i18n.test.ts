import { describe, it, expect } from "vitest";
import { texts, errorText } from "./i18n";
describe("French and Arabic coverage", () => {
  it("has all labels in both languages", () => {
    expect(Object.keys(texts.fr).sort()).toEqual(Object.keys(texts.ar).sort());
    for (const value of Object.values(texts.ar))
      expect(value.length).toBeGreaterThan(0);
  });
  it("translates failure and missing configuration states", () => {
    expect(errorText("ai_not_configured", "fr")).toContain("configuré");
    expect(errorText("invalid_citation", "ar")).toContain("اقتباس");
  });
});

import { chatTexts } from "./chat-i18n";
it("keeps chat controls available in French and Arabic", () => {
  expect(Object.keys(chatTexts.fr).sort()).toEqual(
    Object.keys(chatTexts.ar).sort(),
  );
  expect(chatTexts.fr.placeholder).toContain("question");
  expect(chatTexts.ar.send).toContain("إرسال");
});
