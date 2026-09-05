import asyncio
from datetime import date
from dateutil.relativedelta import relativedelta
from core.infrastructure.provider_hub import ProviderHub
from core.infrastructure.db.catalog_repository import CatalogRepository
from core.domain.services import FinancialEngine
from apps.web.deps import get_indices_sync, get_fx_sync

def test_horizon():
    repo = CatalogRepository()
    provider = ProviderHub(repo)
    indices = get_indices_sync()
    fx = get_fx_sync()
    
    ticker = "AL30"
    inst = repo.get_instrument_by_ticker(ticker)
    snaps = provider.fetch_snapshots([ticker])
    snap = snaps.get(ticker)
    if snap is None:
        print("No snapshot")
        return
    snap.instrument = inst
    
    ref_date = date.today()
    base_tir = FinancialEngine.calculate_tir(snap, indices, fx, settle_date=ref_date)
    
    h_months = 6
    shift_bps = 100
    future_date = ref_date + relativedelta(months=h_months)
    
    future_tir = base_tir + (shift_bps / 10000.0)
    
    # Reprice at future date
    future_price = FinancialEngine.price_from_tir(snap, future_tir, indices, fx, settle_date=future_date)
    
    print(f"Base TIR: {base_tir:.4f}")
    print(f"Future Price in {h_months}M at TIR {future_tir:.4f}: {future_price}")

if __name__ == "__main__":
    test_horizon()
