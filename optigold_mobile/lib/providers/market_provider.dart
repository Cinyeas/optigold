import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api/models/market_snapshot.dart';
import 'api_provider.dart';

final marketSnapshotProvider = FutureProvider<MarketSnapshot>((ref) async {
  final client = await ref.watch(apiClientProvider.future);
  return client.getMarketSnapshot();
});
