import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api/models/signal.dart';
import 'api_provider.dart';

// Latest signal (auto-loads on startup)
final latestSignalProvider = FutureProvider<SignalModel>((ref) async {
  final client = await ref.watch(apiClientProvider.future);
  return client.getLatestSignal();
});

// Manually trigger refresh
final signalRefreshProvider = FutureProvider.autoDispose<SignalModel>((ref) async {
  final client = await ref.watch(apiClientProvider.future);
  return client.refreshSignal();
});

// Signal detail by id
final signalDetailProvider =
    FutureProvider.autoDispose.family<SignalModel, String>((ref, id) async {
  final client = await ref.watch(apiClientProvider.future);
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
    final client = await ref.read(apiClientProvider.future);
    final result = await client.listSignals(page: _page, pageSize: 20);
    _hasMore = result.items.length == 20;
    return result.items;
  }

  Future<void> loadMore() async {
    if (!_hasMore) return;
    _page++;
    final client  = await ref.read(apiClientProvider.future);
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
