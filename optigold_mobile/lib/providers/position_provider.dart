import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api/models/position.dart';
import 'api_provider.dart';

class PositionsNotifier extends AutoDisposeAsyncNotifier<List<PositionModel>> {
  @override
  Future<List<PositionModel>> build() async {
    final client = await ref.watch(apiClientProvider.future);
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
    final client = await ref.read(apiClientProvider.future);
    await client.createPosition({
      'signal_id':   signalId,
      'instrument':  instrument,
      'strategy':    strategy,
      if (strikeA    != null) 'strike_a':    strikeA,
      if (strikeB    != null) 'strike_b':    strikeB,
      if (expiry     != null) 'expiry':      expiry,
      if (quantity   != null) 'quantity':    quantity,
      if (entryPrice != null) 'entry_price': entryPrice,
    });
    ref.invalidateSelf();
  }

  Future<void> close(int id, double closePrice, {String? closeReason, String? notes}) async {
    final client = await ref.read(apiClientProvider.future);
    await client.closePosition(id, closePrice, closeReason: closeReason, notes: notes);
    ref.invalidateSelf();
  }

  Future<void> delete(int id) async {
    final client = await ref.read(apiClientProvider.future);
    await client.deletePosition(id);
    ref.invalidateSelf();
  }
}

final positionsProvider =
    AsyncNotifierProvider.autoDispose<PositionsNotifier, List<PositionModel>>(
        PositionsNotifier.new);
