import { fmtDuration } from "./ui";

/** Value text for an indicator: closure time as days or hours, percentages with %, everything else as a plain number. */
export const showValue = (i: any, v: number | null | undefined) => v == null ? "—" : i.key === "closure_time" ? fmtDuration(v) : `${v}${i.unit === "%" ? "%" : ""}`;
export const unitLabel = (i: any) => (i.key === "closure_time" || i.unit === "%" ? "" : i.unit);
