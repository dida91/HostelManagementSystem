/**
 * Chart colours, validated with the dataviz method on the panel surface #12292F
 * (dark mode). See DESIGN_SYSTEM.md. Do not add hues by eye: re-run the validator.
 */

/** Slot 1: every bar of a single-series chart. */
export const SERIES_1 = "#3987e5";

/** Categorical slots in prayer-flag order (sky, fire, water, earth, then two more). */
export const CATEGORICAL = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9"];

/** One-hue ordinal ramp, light (early) to dark (late). */
export const ORDINAL_SKY = ["#b4d2f6", "#86b4ef", "#5a97e8", "#3a7bd0", "#2e62a6"];

/** Meter track: a dark step of the sky hue, so state reads across the whole bar. */
export const TRACK_SKY = "#1c3a57";
