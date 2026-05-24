require('dotenv').config();

const CONFIG = {
  rpc: process.env.RPC_URL || 'https://rpc-mainnet.supra.com',
  
  wallet: {
    address: process.env.SENDER_ADDRESS || '',
    privateKey: process.env.PRIVATE_KEY || ''
  },
  
  telegram: {
    token: process.env.TELEGRAM_BOT_TOKEN || '',
    chatId: process.env.TELEGRAM_CHAT_ID || ''
  },
  
  trading: {
    minProfitPercent: parseFloat(process.env.MIN_PROFIT_PERCENT) || 0.5,
    maxSlippage: parseFloat(process.env.MAX_SLIPPAGE) || 0.5,
    gasLimit: parseInt(process.env.GAS_LIMIT) || 500000,
    minLiquidityUsd: parseFloat(process.env.MIN_LIQUIDITY_USD) || 1000
  },
  
  cache: {
    balanceTTL: 30000,
    poolTTL: 10000,
    priceTTL: 5000
  },
  
  dexes: {
    dexyln: {
      name: 'Dexyln',
      router: '0x0000000000000000000000000000000000000001',
      factory: '0x0000000000000000000000000000000000000002',
      active: true
    },
    atmos: {
      name: 'Atmos',
      router: '0x0000000000000000000000000000000000000003',
      factory: '0x0000000000000000000000000000000000000004',
      active: true
    },
    spikey: {
      name: 'Spikey',
      router: '0x0000000000000000000000000000000000000005',
      factory: '0x0000000000000000000000000000000000000006',
      active: true
    }
  },
  
  pairs: [
    { base: 'SUPRA', quote: 'USDC' },
    { base: 'SUPRA', quote: 'USDT' },
    { base: 'SUPRA', quote: 'WETH' }
  ]
};

module.exports = { CONFIG };