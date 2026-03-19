import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api/models/user_profile.dart';
import 'api_provider.dart';

class ProfileNotifier extends AsyncNotifier<UserProfile> {
  @override
  Future<UserProfile> build() async {
    final client = await ref.watch(apiClientProvider.future);
    return client.getProfile();
  }

  Future<void> patch(Map<String, dynamic> updates) async {
    final client = await ref.read(apiClientProvider.future);
    final updated = await client.updateProfile(updates);
    state = AsyncData(updated);
  }
}

final profileProvider =
    AsyncNotifierProvider<ProfileNotifier, UserProfile>(ProfileNotifier.new);
