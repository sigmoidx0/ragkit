import type { KeyboardEvent } from "react";

/**
 * An Enter meant to submit — not the one that confirms a Korean/Japanese IME
 * composition. Treating that one as a submit sends the text with its last
 * syllable unfinished, then leaves the syllable behind in the box.
 *
 * Chrome and Firefox flag it with `isComposing`; Safari sends the confirming
 * Enter after compositionend, unflagged but with keyCode 229.
 */
export function isSubmitEnter(e: KeyboardEvent): boolean {
  return e.key === "Enter" && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229;
}
