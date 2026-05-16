import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api/api_client.dart';
import '../core/api/models/market_snapshot.dart';
import 'api_provider.dart';

class MarketSnapshotNotifier extends AsyncNotifier<MarketSnapshot> {
  Timer? _timer;

  @override
  Future<MarketSnapshot> build() async {
    ref.onDispose(() => _timer?.cancel());

    final client = ref.watch(apiClientProvider); // sync — no await

    // Show cached data immediately (no loading flash on startup)
    final cached = client.getCachedMarket();
    if (cached != null) {
      _scheduleRefresh(client);
      return cached;
    }

    // No cache: blocking fetch, then start timer
    final snapshot = await client.getMarketSnapshot();
    _scheduleRefresh(client);
    return snapshot;
  }

  void _scheduleRefresh(ApiClient client) {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 5), (_) async {
      try {
        final snapshot = await client.getMarketSnapshot();
        state = AsyncData(snapshot); // silent update, no loading flash
      } catch (_) {
        // Keep showing stale data on error
      }
    });
  }
}

final marketSnapshotProvider =
    AsyncNotifierProvider<MarketSnapshotNotifier, MarketSnapshot>(
        MarketSnapshotNotifier.new);
