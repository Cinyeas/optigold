import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api/api_client.dart';
import 'prefs_provider.dart';

/// Synchronous provider — resolves immediately since prefs are pre-loaded in main().
final apiClientProvider = Provider<ApiClient>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider);
  return ApiClient.createSync(prefs);
});
