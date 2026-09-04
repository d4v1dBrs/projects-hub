/**
 * Quant Engine for Bonos Argy
 * Contains functions for calculating financial metrics like TIR (XIRR), Duration, and Parity.
 */

const QuantEngine = {
    /**
     * Calculates the time difference in years between two dates using Actual/365 convention.
     */
    yearFracAct365: function(date1, date2) {
        const d1 = new Date(date1);
        const d2 = new Date(date2);
        const msPerDay = 1000 * 60 * 60 * 24;
        const days = (d2 - d1) / msPerDay;
        return days / 365.0;
    },

    /**
     * Calculates the time difference in years between two dates using 30/360 convention.
     */
    yearFrac30360: function(date1, date2) {
        const d1 = new Date(date1);
        const d2 = new Date(date2);
        
        let d1Day = d1.getDate();
        let d1Month = d1.getMonth() + 1;
        let d1Year = d1.getFullYear();
        
        let d2Day = d2.getDate();
        let d2Month = d2.getMonth() + 1;
        let d2Year = d2.getFullYear();
        
        if (d1Day === 31) d1Day = 30;
        if (d2Day === 31 && d1Day === 30) d2Day = 30;
        
        const days = (d2Year - d1Year) * 360 + (d2Month - d1Month) * 30 + (d2Day - d1Day);
        return days / 360.0;
    },

    /**
     * Selects the correct year fraction function based on convention.
     */
    getYearFrac: function(date1, date2, convention) {
        if (convention && convention.toUpperCase() === '30/360') {
            return this.yearFrac30360(date1, date2);
        }
        return this.yearFracAct365(date1, date2);
    },

    /**
     * Calculates Net Present Value (NPV) for a given rate and cashflow.
     * Cashflow expected format: { date: "YYYY-MM-DD", amount: number }
     * The first element is usually the negative price at settlement date.
     */
    calculateNPV: function(rate, cashflows, convention = 'ACT/365') {
        let npv = 0.0;
        if (cashflows.length === 0) return npv;
        
        const settlementDate = cashflows[0].date;
        
        for (let i = 0; i < cashflows.length; i++) {
            const cf = cashflows[i];
            const t = this.getYearFrac(settlementDate, cf.date, convention);
            if (t < 0) continue; // Skip past cashflows
            
            // Continuous compounding or discrete? Standard XIRR uses discrete (1+r)^t
            npv += cf.amount / Math.pow(1 + rate, t);
        }
        return npv;
    },

    /**
     * Calculates XIRR using the Newton-Raphson method.
     */
    calculateXIRR: function(cashflows, convention = 'ACT/365', guess = 0.1) {
        let rate = guess;
        const maxIter = 100;
        const tol = 1e-6;
        
        // Ensure there is at least one negative and one positive cashflow
        let hasPos = false;
        let hasNeg = false;
        for (let cf of cashflows) {
            if (cf.amount > 0) hasPos = true;
            if (cf.amount < 0) hasNeg = true;
        }
        if (!hasPos || !hasNeg) return null; // Cannot calculate TIR

        for (let i = 0; i < maxIter; i++) {
            let npv = this.calculateNPV(rate, cashflows, convention);
            if (Math.abs(npv) < tol) {
                return rate; // Found it
            }
            
            // Derivative of NPV with respect to rate
            let derivative = 0;
            const settlementDate = cashflows[0].date;
            for (let j = 0; j < cashflows.length; j++) {
                const cf = cashflows[j];
                const t = this.getYearFrac(settlementDate, cf.date, convention);
                if (t > 0) {
                    derivative -= (cf.amount * t) / Math.pow(1 + rate, t + 1);
                }
            }
            
            if (Math.abs(derivative) < 1e-12) return null; // Avoid division by zero
            
            const nextRate = rate - (npv / derivative);
            
            if (Math.abs(nextRate - rate) < tol) {
                return nextRate;
            }
            rate = nextRate;
        }
        
        return null; // Did not converge
    },

    /**
     * Calculate Macaulay Duration and Modified Duration
     */
    calculateDurations: function(rate, cashflows, convention = 'ACT/365') {
        let npv = this.calculateNPV(rate, cashflows, convention);
        let macaulay = 0.0;
        
        if (npv === 0) return { macaulay: 0, modified: 0 };
        
        const settlementDate = cashflows[0].date;
        
        for (let i = 0; i < cashflows.length; i++) {
            const cf = cashflows[i];
            if (cf.amount <= 0) continue; // Only positive cashflows for duration
            
            const t = this.getYearFrac(settlementDate, cf.date, convention);
            if (t > 0) {
                const pv = cf.amount / Math.pow(1 + rate, t);
                macaulay += (t * pv) / npv;
            }
        }
        
        const modified = macaulay / (1 + rate);
        return { macaulay: macaulay, modified: modified };
    },

    /**
     * Generate standard cashflow array combining amortizations and coupons
     */
    buildCashflowArray: function(bondData, cleanPrice, settlementDateStr) {
        let cfs = [];
        // First cashflow is the negative price we pay today
        cfs.push({
            date: settlementDateStr,
            amount: -cleanPrice
        });
        
        let remainingPrincipal = parseFloat(bondData.residual_value);
        
        for (let cf of bondData.cashflow) {
            // Check if date is in the future
            if (cf.date >= settlementDateStr) {
                let amortAmount = parseFloat(cf.amortization); // Percentage of total issue usually, or remaining?
                let couponAmount = parseFloat(cf.coupon);
                
                // Assuming cashflow table has absolute cash amounts per 100 VN
                // For simplicity, let's treat amortization and coupon directly as they come from the CSV
                let totalPayment = amortAmount + couponAmount;
                if (totalPayment > 0) {
                    cfs.push({
                        date: cf.date,
                        amount: totalPayment
                    });
                }
            }
        }
        return cfs;
    }
};
