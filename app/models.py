from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RawTokenAmount(BaseModel):
    decimals: int
    tokenAmount: str


class TokenBalanceChange(BaseModel):
    mint: str
    rawTokenAmount: RawTokenAmount
    tokenAccount: str
    userAccount: str


class AccountData(BaseModel):
    account: str
    nativeBalanceChange: int
    tokenBalanceChanges: List[TokenBalanceChange] = []


class Instruction(BaseModel):
    accounts: List[str]
    data: str
    innerInstructions: List[Any] = []
    programId: str


class NativeTransfer(BaseModel):
    amount: int
    fromUserAccount: str
    toUserAccount: str


class TokenTransfer(BaseModel):
    fromTokenAccount: str
    fromUserAccount: str
    mint: str
    toTokenAccount: str
    toUserAccount: str
    tokenAmount: float
    tokenStandard: str


class HeliusTransaction(BaseModel):
    accountData: List[AccountData] = []
    description: str = ""
    events: Dict = {}
    fee: int = 0
    feePayer: str = ""
    instructions: List[Instruction] = []
    nativeTransfers: List[NativeTransfer] = []
    signature: str
    slot: int = 0
    source: str = ""
    timestamp: int = 0
    tokenTransfers: List[TokenTransfer] = []
    transactionError: Optional[Any] = None
    type: str = ""
    
    class Config:
        extra = "allow"


class ScamDetectionResult(BaseModel):
    mint: str
    is_scam: bool
    reasons: List[str] = []
    flags: Dict[str, bool] = {}
    
    has_bundle: bool = False
    has_large_purchase: bool = False
    invalid_metadata_url: bool = False
    invalid_mint_suffix: bool = False
    single_token_dev: Optional[bool] = None
    
    max_purchase_sol: Optional[float] = None
    bundle_index_gap: Optional[int] = None
    total_transactions: int = 0
    first_seen: Optional[int] = None
    last_updated: Optional[int] = None


class TokenMetadata(BaseModel):
    mint: str
    name: Optional[str] = None
    symbol: Optional[str] = None
    uri: Optional[str] = None
    creator: Optional[str] = None
