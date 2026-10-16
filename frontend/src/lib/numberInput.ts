/** A whole number typed by the user: digits only, with no sign, decimal point or spaces inside. */
export const WHOLE_NUMBER_PATTERN = /^\d+$/

/** An amount of money typed by the user: dollars with at most two decimal places, as in 4.50. */
export const PRICE_PATTERN = /^\d+(\.\d{1,2})?$/
