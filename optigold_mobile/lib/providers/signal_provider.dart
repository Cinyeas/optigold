import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api/models/signal.dart';
import 'api_provider.dart';

// Latest signal: shows cache instantly, refreshes silently in background
class LatestSignalNotifier extends AsyncNotifier<SignalModel> {
  @override
  Future<SignalModel> build() async {
    final client = ref.watch(apiClientProvider); // sync — no await

    // Show cached data immediately (no loading flash on startup)
    final cached = client.getCachedSignal();
    if (cached != null) {
      // Background fetch — silent update when done
      Future.microtask(() async {
        try {
          final fresh = await client.getLatestSignal();
          try { state = AsyncData(fresh); } catch (_) {}
        } catch (_) {}
      });
      return cached;
    }

    // No cache: blocking fetch
    return client.getLatestSignal();
  }
}

final latestSignalProvider =
    AsyncNotifierProvider<LatestSignalNotifier, SignalModel>(
        LatestSignalNotifier.new);

// Manually trigger refresh (generates a new signal on the backend)
final signalRefreshProvider = FutureProvider.autoDispose<SignalModel>((ref) async {
  final client = ref.watch(apiClientProvider); // sync
  return client.refreshSignal();
});

// Signal detail by id
final signalDetailProvider =
    FutureProvider.autoDispose.family<SignalModel, String>((ref, id) async {
  final client = ref.watch(apiClientProvider); // sync
  return client.getSignal(id);
});

// Paginated history list
class SignalHistoryNotifier
    extends AutoDisposeAsyncNotifier<List<SignalListItem>> {
  int _page = 1;
  bool _hasMore = true;

  @override
  Future<List<SignalListItem>> build() async {
    _page = 1;
    _hasMore = true;
    return _fetch();
  }

  Future<List<SignalListItem>> _fetch() async {
    final client = ref.read(apiClientProvider); // sync
    final result = await client.listSignals(page: _page, pageSize: 20);
    _hasMore = result.items.length == 20;
    return result.items;
  }

  Future<void> loadMore() async {
    if (!_hasMore) return;
    _page++;
    final client  = ref.read(apiClientProvider); // sync
    final result  = await client.listSignals(page: _page, pageSize: 20);
    final current = state.valueOrNull ?? [];
    state         = AsyncData([...current, ...result.items]);
    _hasMore      = result.items.length == 20;
  }

  bool get hasMore => _hasMore;
}

final signalHistoryProvider =
    AsyncNotifierProvider.autoDispose<SignalHistoryNotifier, List<SignalListItem>>(
        SignalHistoryNotifier.new);
