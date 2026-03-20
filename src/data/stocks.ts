export interface Stock {
  symbol: string;
  name: string;
  sector: string;
  price: number;
  beta: number;
  dividendYield: number;
  marketCap: 'Large' | 'Mid' | 'Small';
  pe: number;
  pbv: number;
  high52w: number;
  low52w: number;
  momentum6M: number; // % return over 6 months
}

export const NSE_STOCKS: Stock[] = [
  // ─── IT ───────────────────────────────────────────────────────────────────
  { symbol: 'TCS', name: 'Tata Consultancy Services', sector: 'IT', price: 4100, beta: 0.65, dividendYield: 1.2, marketCap: 'Large', pe: 32, pbv: 14, high52w: 4592, low52w: 3311, momentum6M: 5.2 },
  { symbol: 'INFY', name: 'Infosys', sector: 'IT', price: 1650, beta: 0.80, dividendYield: 2.1, marketCap: 'Large', pe: 27, pbv: 8, high52w: 2006, low52w: 1307, momentum6M: 3.8 },
  { symbol: 'WIPRO', name: 'Wipro', sector: 'IT', price: 520, beta: 0.90, dividendYield: 0.2, marketCap: 'Large', pe: 22, pbv: 4, high52w: 609, low52w: 411, momentum6M: 2.1 },
  { symbol: 'HCLTECH', name: 'HCL Technologies', sector: 'IT', price: 1780, beta: 0.85, dividendYield: 3.4, marketCap: 'Large', pe: 25, pbv: 7, high52w: 2012, low52w: 1412, momentum6M: 8.4 },
  { symbol: 'TECHM', name: 'Tech Mahindra', sector: 'IT', price: 1620, beta: 1.05, dividendYield: 1.1, marketCap: 'Large', pe: 49, pbv: 5, high52w: 1807, low52w: 1098, momentum6M: 11.2 },
  { symbol: 'LTIM', name: 'LTIMindtree', sector: 'IT', price: 5600, beta: 0.95, dividendYield: 0.9, marketCap: 'Large', pe: 35, pbv: 9, high52w: 6770, low52w: 4313, momentum6M: 6.7 },
  { symbol: 'KPITTECH', name: 'KPIT Technologies', sector: 'IT', price: 1400, beta: 1.80, dividendYield: 0.3, marketCap: 'Mid', pe: 82, pbv: 19, high52w: 1929, low52w: 1016, momentum6M: 18.3 },
  { symbol: 'PERSISTENT', name: 'Persistent Systems', sector: 'IT', price: 5800, beta: 1.20, dividendYield: 0.5, marketCap: 'Mid', pe: 64, pbv: 15, high52w: 6788, low52w: 3882, momentum6M: 14.6 },
  { symbol: 'COFORGE', name: 'Coforge', sector: 'IT', price: 6200, beta: 1.30, dividendYield: 0.7, marketCap: 'Mid', pe: 56, pbv: 13, high52w: 8000, low52w: 4406, momentum6M: 20.1 },

  // ─── Banking ──────────────────────────────────────────────────────────────
  { symbol: 'HDFCBANK', name: 'HDFC Bank', sector: 'Banking', price: 1450, beta: 0.95, dividendYield: 1.1, marketCap: 'Large', pe: 19, pbv: 2.5, high52w: 1880, low52w: 1364, momentum6M: -4.1 },
  { symbol: 'ICICIBANK', name: 'ICICI Bank', sector: 'Banking', price: 1080, beta: 1.10, dividendYield: 0.8, marketCap: 'Large', pe: 18, pbv: 3.0, high52w: 1330, low52w: 989, momentum6M: 2.5 },
  { symbol: 'SBIN', name: 'State Bank of India', sector: 'Banking', price: 760, beta: 1.20, dividendYield: 1.5, marketCap: 'Large', pe: 9, pbv: 1.5, high52w: 912, low52w: 680, momentum6M: -6.3 },
  { symbol: 'AXISBANK', name: 'Axis Bank', sector: 'Banking', price: 1120, beta: 1.15, dividendYield: 0.1, marketCap: 'Large', pe: 13, pbv: 1.9, high52w: 1340, low52w: 995, momentum6M: 1.2 },
  { symbol: 'KOTAKBANK', name: 'Kotak Mahindra Bank', sector: 'Banking', price: 1790, beta: 0.85, dividendYield: 0.1, marketCap: 'Large', pe: 21, pbv: 3.0, high52w: 2130, low52w: 1701, momentum6M: -2.8 },
  { symbol: 'INDUSINDBK', name: 'IndusInd Bank', sector: 'Banking', price: 960, beta: 1.40, dividendYield: 1.5, marketCap: 'Large', pe: 10, pbv: 1.3, high52w: 1694, low52w: 861, momentum6M: -24.5 },
  { symbol: 'IDFCFIRSTB', name: 'IDFC First Bank', sector: 'Banking', price: 80, beta: 1.60, dividendYield: 0.0, marketCap: 'Mid', pe: 21, pbv: 1.1, high52w: 99, low52w: 57, momentum6M: -11.2 },
  { symbol: 'FEDERALBNK', name: 'Federal Bank', sector: 'Banking', price: 185, beta: 1.10, dividendYield: 1.6, marketCap: 'Mid', pe: 10, pbv: 1.4, high52w: 216, low52w: 152, momentum6M: 5.8 },

  // ─── Finance / NBFC ───────────────────────────────────────────────────────
  { symbol: 'BAJFINANCE', name: 'Bajaj Finance', sector: 'Finance', price: 6500, beta: 1.40, dividendYield: 0.5, marketCap: 'Large', pe: 28, pbv: 5.4, high52w: 8192, low52w: 6170, momentum6M: -8.4 },
  { symbol: 'BAJAJFINSV', name: 'Bajaj Finserv', sector: 'Finance', price: 1870, beta: 1.25, dividendYield: 0.1, marketCap: 'Large', pe: 18, pbv: 3.2, high52w: 2029, low52w: 1420, momentum6M: 5.1 },
  { symbol: 'CHOLAFIN', name: 'Cholamandalam Finance', sector: 'Finance', price: 1310, beta: 1.45, dividendYield: 0.1, marketCap: 'Mid', pe: 26, pbv: 4.9, high52w: 1652, low52w: 1063, momentum6M: -8.1 },
  { symbol: 'MUTHOOTFIN', name: 'Muthoot Finance', sector: 'Finance', price: 1960, beta: 1.05, dividendYield: 1.1, marketCap: 'Mid', pe: 18, pbv: 3.2, high52w: 2403, low52w: 1341, momentum6M: 16.2 },

  // ─── FMCG ─────────────────────────────────────────────────────────────────
  { symbol: 'HINDUNILVR', name: 'Hindustan Unilever', sector: 'FMCG', price: 2400, beta: 0.50, dividendYield: 1.6, marketCap: 'Large', pe: 55, pbv: 11, high52w: 2731, low52w: 2172, momentum6M: -3.2 },
  { symbol: 'ITC', name: 'ITC Ltd', sector: 'FMCG', price: 430, beta: 0.60, dividendYield: 3.2, marketCap: 'Large', pe: 27, pbv: 7, high52w: 528, low52w: 398, momentum6M: -4.8 },
  { symbol: 'NESTLEIND', name: 'Nestle India', sector: 'FMCG', price: 2500, beta: 0.45, dividendYield: 1.1, marketCap: 'Large', pe: 74, pbv: 50, high52w: 2778, low52w: 2216, momentum6M: -5.7 },
  { symbol: 'BRITANNIA', name: 'Britannia Industries', sector: 'FMCG', price: 5100, beta: 0.55, dividendYield: 1.4, marketCap: 'Large', pe: 55, pbv: 40, high52w: 5794, low52w: 4685, momentum6M: -2.1 },
  { symbol: 'DABUR', name: 'Dabur India', sector: 'FMCG', price: 520, beta: 0.55, dividendYield: 1.0, marketCap: 'Large', pe: 51, pbv: 11, high52w: 658, low52w: 481, momentum6M: -6.1 },
  { symbol: 'MARICO', name: 'Marico', sector: 'FMCG', price: 620, beta: 0.50, dividendYield: 1.5, marketCap: 'Large', pe: 50, pbv: 17, high52w: 722, low52w: 540, momentum6M: 2.1 },
  { symbol: 'GODREJCP', name: 'Godrej Consumer Products', sector: 'FMCG', price: 1160, beta: 0.65, dividendYield: 0.9, marketCap: 'Large', pe: 55, pbv: 9, high52w: 1515, low52w: 1002, momentum6M: -13.2 },

  // ─── Energy ───────────────────────────────────────────────────────────────
  { symbol: 'RELIANCE', name: 'Reliance Industries', sector: 'Energy', price: 2900, beta: 1.00, dividendYield: 0.3, marketCap: 'Large', pe: 27, pbv: 2.3, high52w: 3218, low52w: 2220, momentum6M: 2.1 },
  { symbol: 'ONGC', name: 'ONGC', sector: 'Energy', price: 270, beta: 1.10, dividendYield: 4.5, marketCap: 'Large', pe: 7, pbv: 1.1, high52w: 345, low52w: 221, momentum6M: -7.2 },
  { symbol: 'NTPC', name: 'NTPC', sector: 'Energy', price: 350, beta: 0.85, dividendYield: 2.1, marketCap: 'Large', pe: 17, pbv: 2.4, high52w: 448, low52w: 311, momentum6M: -10.1 },
  { symbol: 'POWERGRID', name: 'Power Grid Corp', sector: 'Energy', price: 310, beta: 0.70, dividendYield: 3.9, marketCap: 'Large', pe: 18, pbv: 3.3, high52w: 366, low52w: 252, momentum6M: -8.8 },
  { symbol: 'ADANIGREEN', name: 'Adani Green Energy', sector: 'Energy', price: 1800, beta: 1.80, dividendYield: 0.0, marketCap: 'Large', pe: 120, pbv: 22, high52w: 2174, low52w: 852, momentum6M: 25.6 },
  { symbol: 'TATAPOWER', name: 'Tata Power', sector: 'Energy', price: 395, beta: 1.60, dividendYield: 0.6, marketCap: 'Mid', pe: 30, pbv: 4.5, high52w: 495, low52w: 328, momentum6M: -5.4 },

  // ─── Pharma ───────────────────────────────────────────────────────────────
  { symbol: 'SUNPHARMA', name: 'Sun Pharma', sector: 'Pharma', price: 1550, beta: 0.70, dividendYield: 0.8, marketCap: 'Large', pe: 34, pbv: 6, high52w: 1960, low52w: 1421, momentum6M: -5.3 },
  { symbol: 'DRREDDY', name: 'Dr Reddys Labs', sector: 'Pharma', price: 6200, beta: 0.75, dividendYield: 0.6, marketCap: 'Large', pe: 19, pbv: 3, high52w: 7620, low52w: 5481, momentum6M: -7.8 },
  { symbol: 'CIPLA', name: 'Cipla', sector: 'Pharma', price: 1450, beta: 0.65, dividendYield: 0.6, marketCap: 'Large', pe: 26, pbv: 4, high52w: 1708, low52w: 1280, momentum6M: -6.2 },
  { symbol: 'APOLLOHOSP', name: 'Apollo Hospitals', sector: 'Pharma', price: 6800, beta: 0.80, dividendYield: 0.4, marketCap: 'Large', pe: 88, pbv: 15, high52w: 7545, low52w: 5001, momentum6M: 11.1 },
  { symbol: 'DIVISLAB', name: 'Divis Laboratories', sector: 'Pharma', price: 4900, beta: 0.70, dividendYield: 0.8, marketCap: 'Large', pe: 52, pbv: 8, high52w: 6236, low52w: 3370, momentum6M: 25.2 },
  { symbol: 'BIOCON', name: 'Biocon', sector: 'Pharma', price: 280, beta: 0.90, dividendYield: 0.0, marketCap: 'Mid', pe: 35, pbv: 2, high52w: 392, low52w: 228, momentum6M: -8.6 },
  { symbol: 'AUROPHARMA', name: 'Aurobindo Pharma', sector: 'Pharma', price: 1120, beta: 0.85, dividendYield: 0.4, marketCap: 'Large', pe: 16, pbv: 2, high52w: 1592, low52w: 920, momentum6M: 3.6 },

  // ─── Auto ─────────────────────────────────────────────────────────────────
  { symbol: 'TATAMOTORS', name: 'Tata Motors', sector: 'Auto', price: 980, beta: 1.50, dividendYield: 0.2, marketCap: 'Large', pe: 8, pbv: 3, high52w: 1179, low52w: 729, momentum6M: -7.6 },
  { symbol: 'M&M', name: 'Mahindra & Mahindra', sector: 'Auto', price: 1900, beta: 1.20, dividendYield: 0.9, marketCap: 'Large', pe: 27, pbv: 5, high52w: 3264, low52w: 1876, momentum6M: -18.5 },
  { symbol: 'MARUTI', name: 'Maruti Suzuki', sector: 'Auto', price: 11500, beta: 1.00, dividendYield: 0.8, marketCap: 'Large', pe: 27, pbv: 4, high52w: 13680, low52w: 9959, momentum6M: 5.7 },
  { symbol: 'BAJAJ-AUTO', name: 'Bajaj Auto', sector: 'Auto', price: 8900, beta: 0.90, dividendYield: 1.5, marketCap: 'Large', pe: 29, pbv: 9, high52w: 12774, low52w: 7627, momentum6M: -11.5 },
  { symbol: 'HEROMOTOCO', name: 'Hero MotoCorp', sector: 'Auto', price: 4700, beta: 0.85, dividendYield: 2.4, marketCap: 'Large', pe: 20, pbv: 6, high52w: 5680, low52w: 3910, momentum6M: 4.2 },
  { symbol: 'EICHERMOT', name: 'Eicher Motors', sector: 'Auto', price: 4900, beta: 1.10, dividendYield: 0.8, marketCap: 'Large', pe: 30, pbv: 9, high52w: 5520, low52w: 3525, momentum6M: 5.8 },
  { symbol: 'TVSMOTOR', name: 'TVS Motor', sector: 'Auto', price: 2400, beta: 1.30, dividendYield: 0.5, marketCap: 'Mid', pe: 52, pbv: 17, high52w: 2958, low52w: 1848, momentum6M: -4.1 },

  // ─── Metals ───────────────────────────────────────────────────────────────
  { symbol: 'TATASTEEL', name: 'Tata Steel', sector: 'Metals', price: 150, beta: 1.60, dividendYield: 2.4, marketCap: 'Large', pe: 20, pbv: 1.6, high52w: 185, low52w: 120, momentum6M: -8.1 },
  { symbol: 'JSWSTEEL', name: 'JSW Steel', sector: 'Metals', price: 850, beta: 1.40, dividendYield: 0.4, marketCap: 'Large', pe: 24, pbv: 2.3, high52w: 1063, low52w: 760, momentum6M: -11.4 },
  { symbol: 'HINDALCO', name: 'Hindalco', sector: 'Metals', price: 580, beta: 1.50, dividendYield: 0.5, marketCap: 'Large', pe: 10, pbv: 1.5, high52w: 772, low52w: 502, momentum6M: -11.9 },
  { symbol: 'VEDL', name: 'Vedanta Ltd', sector: 'Metals', price: 440, beta: 1.60, dividendYield: 6.8, marketCap: 'Large', pe: 10, pbv: 2.5, high52w: 527, low52w: 225, momentum6M: 11.2 },
  { symbol: 'COALINDIA', name: 'Coal India', sector: 'Metals', price: 410, beta: 1.00, dividendYield: 5.6, marketCap: 'Large', pe: 8, pbv: 3.8, high52w: 544, low52w: 378, momentum6M: -10.4 },
  { symbol: 'NMDC', name: 'NMDC', sector: 'Metals', price: 220, beta: 1.25, dividendYield: 3.5, marketCap: 'Mid', pe: 8, pbv: 1.8, high52w: 286, low52w: 178, momentum6M: -6.8 },

  // ─── Consumer Durables ────────────────────────────────────────────────────
  { symbol: 'POLYCAB', name: 'Polycab India', sector: 'Consumer Durables', price: 4800, beta: 1.30, dividendYield: 0.6, marketCap: 'Mid', pe: 48, pbv: 10, high52w: 7600, low52w: 4270, momentum6M: -21.5 },
  { symbol: 'DIXON', name: 'Dixon Technologies', sector: 'Consumer Durables', price: 7200, beta: 1.70, dividendYield: 0.1, marketCap: 'Mid', pe: 153, pbv: 33, high52w: 19220, low52w: 6541, momentum6M: -42.8 },
  { symbol: 'HAVELLS', name: 'Havells India', sector: 'Consumer Durables', price: 1460, beta: 1.00, dividendYield: 0.7, marketCap: 'Large', pe: 71, pbv: 13, high52w: 2029, low52w: 1330, momentum6M: -13.5 },
  { symbol: 'VOLTAS', name: 'Voltas', sector: 'Consumer Durables', price: 1370, beta: 1.20, dividendYield: 0.5, marketCap: 'Mid', pe: 80, pbv: 7, high52w: 1945, low52w: 1054, momentum6M: 8.6 },

  // ─── Infrastructure / Capital Goods ───────────────────────────────────────
  { symbol: 'LT', name: 'Larsen & Toubro', sector: 'Infra', price: 3500, beta: 1.10, dividendYield: 0.9, marketCap: 'Large', pe: 31, pbv: 5, high52w: 3964, low52w: 3074, momentum6M: -2.9 },
  { symbol: 'SIEMENS', name: 'Siemens India', sector: 'Infra', price: 6200, beta: 1.00, dividendYield: 0.3, marketCap: 'Large', pe: 68, pbv: 14, high52w: 8169, low52w: 5574, momentum6M: -11.8 },
  { symbol: 'ABB', name: 'ABB India', sector: 'Infra', price: 5800, beta: 1.10, dividendYield: 0.2, marketCap: 'Mid', pe: 76, pbv: 18, high52w: 9312, low52w: 5620, momentum6M: -24.0 },
  { symbol: 'BHEL', name: 'BHEL', sector: 'Infra', price: 225, beta: 1.70, dividendYield: 0.9, marketCap: 'Large', pe: 70, pbv: 2.8, high52w: 335, low52w: 180, momentum6M: -13.9 },
  { symbol: 'IRFC', name: 'IRFC', sector: 'Infra', price: 160, beta: 1.30, dividendYield: 1.2, marketCap: 'Large', pe: 29, pbv: 4.5, high52w: 229, low52w: 131, momentum6M: -14.2 },

  // ─── Telecom ──────────────────────────────────────────────────────────────
  { symbol: 'BHARTIARTL', name: 'Bharti Airtel', sector: 'Telecom', price: 1560, beta: 0.75, dividendYield: 0.4, marketCap: 'Large', pe: 79, pbv: 7, high52w: 1779, low52w: 1250, momentum6M: 5.4 },
  { symbol: 'INDUSTOWER', name: 'Indus Towers', sector: 'Telecom', price: 340, beta: 0.80, dividendYield: 2.9, marketCap: 'Large', pe: 18, pbv: 2.8, high52w: 440, low52w: 296, momentum6M: -9.8 },

  // ─── Cement ───────────────────────────────────────────────────────────────
  { symbol: 'ULTRACEMCO', name: 'UltraTech Cement', sector: 'Cement', price: 11200, beta: 1.00, dividendYield: 0.4, marketCap: 'Large', pe: 46, pbv: 6, high52w: 12144, low52w: 9343, momentum6M: -2.7 },
  { symbol: 'SHREECEM', name: 'Shree Cement', sector: 'Cement', price: 27000, beta: 0.90, dividendYield: 0.2, marketCap: 'Large', pe: 46, pbv: 6, high52w: 31099, low52w: 21218, momentum6M: -4.0 },
  { symbol: 'AMBUJACEM', name: 'Ambuja Cements', sector: 'Cement', price: 560, beta: 1.00, dividendYield: 0.3, marketCap: 'Large', pe: 36, pbv: 3, high52w: 668, low52w: 435, momentum6M: -3.5 },

  // ─── Insurance ────────────────────────────────────────────────────────────
  { symbol: 'SBILIFE', name: 'SBI Life Insurance', sector: 'Insurance', price: 1460, beta: 0.80, dividendYield: 0.0, marketCap: 'Large', pe: 66, pbv: 10, high52w: 1935, low52w: 1300, momentum6M: -12.5 },
  { symbol: 'HDFCLIFE', name: 'HDFC Life Insurance', sector: 'Insurance', price: 640, beta: 0.75, dividendYield: 0.4, marketCap: 'Large', pe: 72, pbv: 8, high52w: 761, low52w: 511, momentum6M: 5.8 },
  { symbol: 'ICICIGI', name: 'ICICI Lombard', sector: 'Insurance', price: 1840, beta: 0.70, dividendYield: 0.6, marketCap: 'Large', pe: 48, pbv: 7, high52w: 2301, low52w: 1596, momentum6M: -5.6 },

  // ─── Real Estate ──────────────────────────────────────────────────────────
  { symbol: 'DLF', name: 'DLF', sector: 'Real Estate', price: 680, beta: 1.40, dividendYield: 0.7, marketCap: 'Large', pe: 39, pbv: 4, high52w: 967, low52w: 601, momentum6M: -16.4 },
  { symbol: 'GODREJPROP', name: 'Godrej Properties', sector: 'Real Estate', price: 2200, beta: 1.50, dividendYield: 0.0, marketCap: 'Large', pe: 52, pbv: 6, high52w: 3402, low52w: 1761, momentum6M: -22.8 },
  { symbol: 'PRESTIGE', name: 'Prestige Estates', sector: 'Real Estate', price: 1540, beta: 1.60, dividendYield: 0.2, marketCap: 'Mid', pe: 50, pbv: 6, high52w: 2200, low52w: 1250, momentum6M: -16.2 },

  // ─── Chemicals ────────────────────────────────────────────────────────────
  { symbol: 'PIDILITIND', name: 'Pidilite Industries', sector: 'Chemicals', price: 2900, beta: 0.70, dividendYield: 0.6, marketCap: 'Large', pe: 82, pbv: 19, high52w: 3390, low52w: 2482, momentum6M: -4.9 },
  { symbol: 'SRF', name: 'SRF', sector: 'Chemicals', price: 2400, beta: 1.10, dividendYield: 0.3, marketCap: 'Mid', pe: 38, pbv: 6, high52w: 2836, low52w: 1980, momentum6M: -2.6 },
  { symbol: 'DEEPAKNITRITE', name: 'Deepak Nitrite', sector: 'Chemicals', price: 2000, beta: 1.30, dividendYield: 0.4, marketCap: 'Mid', pe: 22, pbv: 5, high52w: 2925, low52w: 1821, momentum6M: -13.6 },

  // ─── Small Cap Growth ─────────────────────────────────────────────────────
  { symbol: 'ZOMATO', name: 'Zomato', sector: 'Tech/Internet', price: 220, beta: 2.00, dividendYield: 0.0, marketCap: 'Mid', pe: 220, pbv: 12, high52w: 305, low52w: 124, momentum6M: 24.5 },
  { symbol: 'PAYTM', name: 'One97 Communications', sector: 'Tech/Internet', price: 590, beta: 2.20, dividendYield: 0.0, marketCap: 'Mid', pe: 0, pbv: 2, high52w: 1062, low52w: 310, momentum6M: 15.2 },
  { symbol: 'DELHIVERY', name: 'Delhivery', sector: 'Logistics', price: 340, beta: 1.80, dividendYield: 0.0, marketCap: 'Mid', pe: 0, pbv: 2, high52w: 518, low52w: 280, momentum6M: -8.3 },
  { symbol: 'IRCTC', name: 'IRCTC', sector: 'Tourism', price: 780, beta: 1.40, dividendYield: 0.6, marketCap: 'Mid', pe: 55, pbv: 14, high52w: 1010, low52w: 640, momentum6M: -8.2 },
  { symbol: 'NYKAA', name: 'FSN E-Commerce (Nykaa)', sector: 'Tech/Internet', price: 165, beta: 2.10, dividendYield: 0.0, marketCap: 'Mid', pe: 620, pbv: 13, high52w: 238, low52w: 117, momentum6M: 14.8 },
];

export const LIQUID_ASSETS: Stock[] = [
  { symbol: 'GOLDBEES', name: 'Nippon Gold ETF', sector: 'Gold', price: 62, beta: 0.05, dividendYield: 0.0, marketCap: 'Large', pe: 0, pbv: 1, high52w: 65, low52w: 50, momentum6M: 12.0 },
  { symbol: 'LIQUIDBEES', name: 'Nippon Liquid ETF', sector: 'Liquid', price: 1000, beta: 0.01, dividendYield: 6.5, marketCap: 'Large', pe: 0, pbv: 1, high52w: 1001, low52w: 999, momentum6M: 3.5 },
  { symbol: 'NIFTYBEES', name: 'Nifty 50 ETF', sector: 'Index', price: 245, beta: 1.00, dividendYield: 1.0, marketCap: 'Large', pe: 22, pbv: 3, high52w: 285, low52w: 196, momentum6M: 2.8 },
  { symbol: 'JUNIORBEES', name: 'Nifty Next 50 ETF', sector: 'Index', price: 590, beta: 1.15, dividendYield: 0.8, marketCap: 'Large', pe: 24, pbv: 3, high52w: 745, low52w: 557, momentum6M: -3.2 },
  { symbol: 'SILVERBEES', name: 'Silver ETF', sector: 'Silver', price: 100, beta: 0.15, dividendYield: 0.0, marketCap: 'Large', pe: 0, pbv: 1, high52w: 110, low52w: 80, momentum6M: 8.5 },
];

// Sector correlation matrix (simplified, symmetric)
// Values are approximate pairwise correlations between sectors
export const SECTOR_CORRELATIONS: { [key: string]: { [key: string]: number } } = {
  IT: { IT: 1.00, Banking: 0.60, Finance: 0.55, FMCG: 0.25, Energy: 0.35, Pharma: 0.30, Auto: 0.55, Metals: 0.45, 'Consumer Durables': 0.50, Infra: 0.40, Telecom: 0.30, Cement: 0.38, Insurance: 0.45, 'Real Estate': 0.35, Chemicals: 0.40, 'Tech/Internet': 0.70, Logistics: 0.45, Tourism: 0.40, Gold: -0.10, Liquid: -0.30, Index: 0.80 },
  Banking: { IT: 0.60, Banking: 1.00, Finance: 0.85, FMCG: 0.30, Energy: 0.50, Pharma: 0.35, Auto: 0.65, Metals: 0.55, 'Consumer Durables': 0.45, Infra: 0.60, Telecom: 0.40, Cement: 0.55, Insurance: 0.70, 'Real Estate': 0.60, Chemicals: 0.45, 'Tech/Internet': 0.50, Logistics: 0.45, Tourism: 0.50, Gold: -0.15, Liquid: -0.35, Index: 0.90 },
  Finance: { IT: 0.55, Banking: 0.85, Finance: 1.00, FMCG: 0.28, Energy: 0.45, Pharma: 0.32, Auto: 0.62, Metals: 0.50, 'Consumer Durables': 0.42, Infra: 0.55, Telecom: 0.38, Cement: 0.50, Insurance: 0.75, 'Real Estate': 0.65, Chemicals: 0.42, 'Tech/Internet': 0.48, Logistics: 0.42, Tourism: 0.48, Gold: -0.12, Liquid: -0.32, Index: 0.85 },
  FMCG: { IT: 0.25, Banking: 0.30, Finance: 0.28, FMCG: 1.00, Energy: 0.20, Pharma: 0.55, Auto: 0.40, Metals: 0.15, 'Consumer Durables': 0.60, Infra: 0.25, Telecom: 0.35, Cement: 0.28, Insurance: 0.30, 'Real Estate': 0.22, Chemicals: 0.52, 'Tech/Internet': 0.20, Logistics: 0.30, Tourism: 0.35, Gold: 0.10, Liquid: -0.05, Index: 0.55 },
  Energy: { IT: 0.35, Banking: 0.50, Finance: 0.45, FMCG: 0.20, Energy: 1.00, Pharma: 0.25, Auto: 0.50, Metals: 0.65, 'Consumer Durables': 0.40, Infra: 0.70, Telecom: 0.35, Cement: 0.60, Insurance: 0.40, 'Real Estate': 0.50, Chemicals: 0.55, 'Tech/Internet': 0.30, Logistics: 0.45, Tourism: 0.40, Gold: 0.15, Liquid: -0.25, Index: 0.75 },
  Pharma: { IT: 0.30, Banking: 0.35, Finance: 0.32, FMCG: 0.55, Energy: 0.25, Pharma: 1.00, Auto: 0.30, Metals: 0.20, 'Consumer Durables': 0.42, Infra: 0.28, Telecom: 0.32, Cement: 0.25, Insurance: 0.38, 'Real Estate': 0.20, Chemicals: 0.60, 'Tech/Internet': 0.28, Logistics: 0.28, Tourism: 0.30, Gold: 0.05, Liquid: -0.10, Index: 0.60 },
  Auto: { IT: 0.55, Banking: 0.65, Finance: 0.62, FMCG: 0.40, Energy: 0.50, Pharma: 0.30, Auto: 1.00, Metals: 0.70, 'Consumer Durables': 0.65, Infra: 0.60, Telecom: 0.40, Cement: 0.55, Insurance: 0.50, 'Real Estate': 0.48, Chemicals: 0.48, 'Tech/Internet': 0.45, Logistics: 0.60, Tourism: 0.50, Gold: -0.05, Liquid: -0.30, Index: 0.80 },
  Metals: { IT: 0.45, Banking: 0.55, Finance: 0.50, FMCG: 0.15, Energy: 0.65, Pharma: 0.20, Auto: 0.70, Metals: 1.00, 'Consumer Durables': 0.50, Infra: 0.65, Telecom: 0.30, Cement: 0.70, Insurance: 0.40, 'Real Estate': 0.55, Chemicals: 0.55, 'Tech/Internet': 0.38, Logistics: 0.50, Tourism: 0.40, Gold: 0.20, Liquid: -0.30, Index: 0.75 },
  Gold: { IT: -0.10, Banking: -0.15, Finance: -0.12, FMCG: 0.10, Energy: 0.15, Pharma: 0.05, Auto: -0.05, Metals: 0.20, 'Consumer Durables': 0.00, Infra: 0.08, Telecom: 0.05, Cement: 0.05, Insurance: 0.00, 'Real Estate': 0.10, Chemicals: 0.08, 'Tech/Internet': -0.12, Logistics: 0.00, Tourism: 0.05, Gold: 1.00, Liquid: 0.05, Index: 0.10 },
  Liquid: { IT: -0.30, Banking: -0.35, Finance: -0.32, FMCG: -0.05, Energy: -0.25, Pharma: -0.10, Auto: -0.30, Metals: -0.30, 'Consumer Durables': -0.20, Infra: -0.28, Telecom: -0.20, Cement: -0.25, Insurance: -0.22, 'Real Estate': -0.28, Chemicals: -0.22, 'Tech/Internet': -0.32, Logistics: -0.25, Tourism: -0.20, Gold: 0.05, Liquid: 1.00, Index: -0.20 },
};
