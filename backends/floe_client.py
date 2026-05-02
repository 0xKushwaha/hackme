"""
Floe Credit Layer — LangChain Integration
==========================================
Wraps the official `floe-agentkit-actions` SDK as LangChain tools so the
existing multi-agent pipeline can borrow USDC on Base without touching
wallet logic inside each agent.

Setup (add to .env):
    FLOE_PRIVATE_KEY=0x...        # EVM wallet private key (controls collateral)
    FLOE_RPC_URL=https://...      # Base mainnet RPC (e.g. from Alchemy / Infura)
    FLOE_MARKET_ID=0x...          # bytes32 market ID — get from FloeClient.get_markets()

Usage:
    client  = FloeClient()
    tools   = client.as_langchain_tools()   # pass to any LangChain agent
    summary = client.get_markets()
    result  = client.instant_borrow(
                  market_id=...,
                  borrow_amount_usdc=1000.0,
                  collateral_eth=0.5,
                  max_rate_bps=800,
                  duration_days=14,
              )

Install dependencies:
    pip install floe-agentkit-actions coinbase-agentkit web3
"""

from __future__ import annotations

import os
from typing import Any

# ── SDK imports ────────────────────────────────────────────────────────
from floe_agentkit_actions import FloeActionProvider, FloeConfig
from coinbase_agentkit import (
    EthAccountWalletProvider,
    EthAccountWalletProviderConfig,
)
from eth_account import Account


class FloeError(Exception):
    pass


# Base mainnet chain ID
_BASE_CHAIN_ID = "8453"


class FloeClient:
    """
    Wraps FloeActionProvider as a plain Python client and as LangChain tools.

    All on-chain actions are executed via the wallet whose private key is in
    FLOE_PRIVATE_KEY. The wallet must hold WETH or cbBTC on Base as collateral
    before any borrow actions will succeed.
    """

    def __init__(
        self,
        private_key: str | None = None,
        rpc_url:     str | None = None,
        market_id:   str | None = None,
    ):
        pk  = private_key or os.getenv("FLOE_PRIVATE_KEY", "")
        rpc = rpc_url     or os.getenv("FLOE_RPC_URL",     "")
        self.market_id = market_id or os.getenv("FLOE_MARKET_ID", "")

        if not pk:
            raise FloeError(
                "No FLOE_PRIVATE_KEY found. Set it in .env.\n"
                "This is the EVM private key for the wallet that holds your collateral."
            )
        if not rpc:
            raise FloeError(
                "No FLOE_RPC_URL found. Set it in .env.\n"
                "Use a Base mainnet RPC from Alchemy, Infura, or Coinbase."
            )

        account = Account.from_key(pk)

        wallet_config = EthAccountWalletProviderConfig(
            account=account,
            chain_id=_BASE_CHAIN_ID,
            rpc_url=rpc,
        )
        self._wallet   = EthAccountWalletProvider(config=wallet_config)
        self._provider = FloeActionProvider(
            config=FloeConfig(
                rpc_url=rpc,
                known_market_ids=[self.market_id] if self.market_id else [],
            )
        )

    # ------------------------------------------------------------------ #
    # Core actions                                                         #
    # ------------------------------------------------------------------ #

    def get_markets(self, market_ids: list[str] | None = None) -> str:
        """List available Floe lending markets and their terms."""
        args: dict[str, Any] = {}
        if market_ids:
            args["market_ids"] = market_ids
        return self._provider.get_markets(self._wallet, args)

    def instant_borrow(
        self,
        borrow_amount_usdc:    float,
        collateral_eth:        float,
        max_rate_bps:          int   = 800,
        duration_days:         int   = 14,
        market_id:             str   | None = None,
        min_ltv_bps:           int   = 8000,
    ) -> str:
        """
        Auto-select the best lender and borrow USDC in one call.

        Args:
            borrow_amount_usdc:  USDC to borrow (e.g. 1000.0 → $1,000).
            collateral_eth:      WETH collateral to post (e.g. 0.5 → 0.5 ETH).
            max_rate_bps:        APR cap in basis points (default 800 = 8%).
            duration_days:       Loan duration in days (default 14).
            market_id:           bytes32 market ID (defaults to FLOE_MARKET_ID).
            min_ltv_bps:         Minimum LTV in bps (default 8000 = 80%).

        Returns:
            String confirmation with loanId, rate, and USDC received.
        """
        mid = market_id or self.market_id
        if not mid:
            raise FloeError(
                "No market_id provided. Pass it explicitly or set FLOE_MARKET_ID in .env."
            )

        return self._provider.instant_borrow(self._wallet, {
            "market_id":            mid,
            "borrow_amount":        str(int(borrow_amount_usdc * 1_000_000)),    # 6 decimals
            "collateral_amount":    str(int(collateral_eth * 10**18)),           # 18 decimals
            "max_interest_rate_bps": str(max_rate_bps),
            "duration":             str(duration_days * 86_400),
            "min_ltv_bps":          str(min_ltv_bps),
        })

    def check_loan_health(self, loan_id: str) -> str:
        """Check LTV, health status, accrued interest, and liquidation distance."""
        return self._provider.check_loan_health(self._wallet, {"loan_id": loan_id})

    def check_credit_status(self, loan_id: str) -> str:
        """View accrued interest, time to expiry, and early repayment cost."""
        return self._provider.check_credit_status(self._wallet, {"loan_id": loan_id})

    def repay_credit(self, loan_id: str, slippage_bps: int = 500) -> str:
        """Repay an outstanding loan."""
        return self._provider.repay_credit(self._wallet, {
            "loan_id":      loan_id,
            "slippage_bps": str(slippage_bps),
        })

    def repay_and_reborrow(
        self,
        loan_id:         str,
        new_borrow_usdc: float | None = None,
        new_collateral_eth: float | None = None,
        max_rate_bps:    int | None = None,
        duration_days:   int | None = None,
    ) -> str:
        """Roll over an existing loan into a new one atomically."""
        args: dict[str, Any] = {"loan_id": loan_id, "slippage_bps": "500"}
        if new_borrow_usdc is not None:
            args["new_borrow_amount"] = str(int(new_borrow_usdc * 1_000_000))
        if new_collateral_eth is not None:
            args["new_collateral_amount"] = str(int(new_collateral_eth * 10**18))
        if max_rate_bps is not None:
            args["max_interest_rate_bps"] = str(max_rate_bps)
        if duration_days is not None:
            args["duration"] = str(duration_days * 86_400)
        return self._provider.repay_and_reborrow(self._wallet, args)

    def add_collateral(self, loan_id: str, amount_eth: float) -> str:
        """Add collateral to an existing loan to lower its LTV."""
        return self._provider.add_collateral(self._wallet, {
            "loan_id": loan_id,
            "amount":  str(int(amount_eth * 10**18)),
        })

    def get_my_loans(self) -> str:
        """Return all active loans for the agent wallet."""
        return self._provider.get_my_loans(self._wallet, {})

    def request_credit(
        self,
        market_id:    str | None = None,
        max_rate_bps: int | None = None,
        max_results:  int = 10,
    ) -> str:
        """Browse available lend offers before committing to a match."""
        mid = market_id or self.market_id
        args: dict[str, Any] = {"max_results": max_results}
        if mid:
            args["market_id"] = mid
        if max_rate_bps is not None:
            args["max_rate_bps"] = str(max_rate_bps)
        return self._provider.request_credit(self._wallet, args)

    # ------------------------------------------------------------------ #
    # LangChain tool wrappers                                              #
    # ------------------------------------------------------------------ #

    def as_langchain_tools(self) -> list:
        """
        Return a list of LangChain Tool objects wrapping the key Floe actions.
        Pass this list to any LangChain agent's tools= parameter.

        Example:
            from langchain.agents import initialize_agent
            tools = floe_client.as_langchain_tools()
            agent = initialize_agent(tools, llm, ...)
        """
        from langchain_core.tools import Tool

        return [
            Tool(
                name="floe_get_markets",
                description=(
                    "List available Floe lending markets on Base. "
                    "Returns market IDs, collateral tokens, loan tokens, "
                    "interest rate floors, and LTV limits."
                ),
                func=lambda _: self.get_markets(),
            ),
            Tool(
                name="floe_instant_borrow",
                description=(
                    "Borrow USDC instantly against WETH collateral on Base via Floe. "
                    "Input must be JSON with keys: borrow_amount_usdc (float), "
                    "collateral_eth (float), max_rate_bps (int, default 800), "
                    "duration_days (int, default 14). "
                    "Returns loan ID, matched rate, and USDC received."
                ),
                func=self._langchain_instant_borrow,
            ),
            Tool(
                name="floe_check_loan_health",
                description=(
                    "Check the health of an active Floe loan. "
                    "Input: loan_id (string). "
                    "Returns LTV, health status, accrued interest, and distance to liquidation."
                ),
                func=lambda loan_id: self.check_loan_health(loan_id.strip()),
            ),
            Tool(
                name="floe_get_my_loans",
                description="List all active Floe loans for the agent wallet.",
                func=lambda _: self.get_my_loans(),
            ),
            Tool(
                name="floe_repay_credit",
                description=(
                    "Repay an active Floe loan. Input: loan_id (string)."
                ),
                func=lambda loan_id: self.repay_credit(loan_id.strip()),
            ),
        ]

    def _langchain_instant_borrow(self, input_str: str) -> str:
        import json
        try:
            params = json.loads(input_str)
        except json.JSONDecodeError:
            return "Error: input must be a JSON object with borrow_amount_usdc, collateral_eth, etc."
        return self.instant_borrow(
            borrow_amount_usdc=float(params["borrow_amount_usdc"]),
            collateral_eth=float(params["collateral_eth"]),
            max_rate_bps=int(params.get("max_rate_bps", 800)),
            duration_days=int(params.get("duration_days", 14)),
        )

    # ------------------------------------------------------------------ #
    # Utility                                                              #
    # ------------------------------------------------------------------ #

    @property
    def wallet_address(self) -> str:
        """The EVM address of the agent wallet."""
        return self._wallet.get_address()
