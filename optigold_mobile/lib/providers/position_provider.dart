import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api/models/position.dart';
import 'api_provider.dart';

class PositionsNotifier extends AutoDisposeAsyncNotifier<List<PositionModel>> {
  @override
  Future<List<PositionModel>> build() async {
    final client = ref.watch(apiClientProvider);
    return client.listPositions();
  }

  Future<void> confirmTrade({
    required String signalId,
    required String instrument,
    required String strategy,
    double? strikeA,
    double? strikeB,
    String? expiry,
    int? quantity,
    double? entryPrice,
  }) async {
    final client = ref.read(apiClientProvider);
    final newPosition = await client.createPosition({
      'signal_id':   signalId,
      'instrument':  instrument,
      'strategy':    strategy,
      if (strikeA    != null) 'strike_a':    strikeA,
      if (strikeB    != null) 'strike_b':    strikeB,
      if (expiry     != null) 'expiry':      expiry,
      if (quantity   != null) 'quantity':    quantity,
      if (entryPrice != null) 'entry_price': entryPrice,
    });
    // Update state directly — no loading flash
    final current = state.valueOrNull ?? [];
    state = AsyncData([...current, newPosition]);
  }

  Future<void> edit(int id, Map<String, dynamic> data) async {
    final client = ref.read(apiClientProvider);
    final updated = await client.updatePosition(id, data);
    final current = state.valueOrNull ?? [];
    state = AsyncData(current.map((p) => p.id == id ? updated : p).toList());
  }

  Future<void> close(int id, double closePrice, {String? closeReason, String? notes}) async {
    final client = ref.read(apiClientProvider);
    final updated = await client.closePosition(id, closePrice,
        closeReason: closeReason, notes: notes);
    // Replace the updated position in-place — no loading flash
    final current = state.valueOrNull ?? [];
    state = AsyncData(current.map((p) => p.id == id ? updated : p).toList());
  }

  Future<void> delete(int id) async {
    final client = ref.read(apiClientProvider);
    await client.deletePosition(id);
    // Remove deleted position in-place — no loading flash
    final current = state.valueOrNull ?? [];
    state = AsyncData(current.where((p) => p.id != id).toList());
  }
}

final positionsProvider =
    AsyncNotifierProvider.autoDispose<PositionsNotifier, List<PositionModel>>(
        PositionsNotifier.new);
