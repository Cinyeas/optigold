import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/colors.dart';
import '../../core/theme/typography.dart';
import '../../core/utils/constants.dart';
import '../../providers/profile_provider.dart';
import '../../providers/prefs_provider.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _urlController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadUrl();
  }

  void _loadUrl() {
    final prefs = ref.read(sharedPreferencesProvider);
    _urlController.text =
        prefs.getString(AppConstants.baseUrlKey) ?? AppConstants.defaultBaseUrl;
  }

  @override
  Widget build(BuildContext context) {
    final profileAsync = ref.watch(profileProvider);

    final body = SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Profile section
          _SectionHeader('Risk Profile'),
          const SizedBox(height: 8),
          profileAsync.when(
            data: (p) => _ProfileCard(profile: p),
            loading: () => const Center(child: CircularProgressIndicator(color: AppColors.primary)),
            error: (e, _) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Row(
                children: [
                  const Icon(Icons.wifi_off, color: AppColors.textMuted, size: 18),
                  const SizedBox(width: 8),
                  Text('Backend offline — connect to load profile',
                      style: AppTypography.bodyRegular.copyWith(color: AppColors.textMuted)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            style: OutlinedButton.styleFrom(
              foregroundColor: AppColors.primary,
              side: const BorderSide(color: AppColors.primary),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              minimumSize: const Size.fromHeight(44),
            ),
            icon: const Icon(Icons.tune, size: 16),
            label: const Text('重新配置风险偏好'),
            onPressed: () async {
              await ref.read(sharedPreferencesProvider).remove(AppConstants.onboardedKey);
              if (context.mounted) context.go('/onboarding');
            },
          ),
          const SizedBox(height: 24),

          // Backend URL
          _SectionHeader('Backend'),
          const SizedBox(height: 8),
          _SettingCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('API Server URL', style: AppTypography.bodyMedium),
                const SizedBox(height: 8),
                TextField(
                  controller: _urlController,
                  style: AppTypography.bodyRegular.copyWith(color: AppColors.textPrimary),
                  decoration: InputDecoration(
                    hintText: AppConstants.defaultBaseUrl,
                    hintStyle: const TextStyle(color: AppColors.textMuted),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: const BorderSide(color: AppColors.divider),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: const BorderSide(color: AppColors.primary),
                    ),
                    filled: true,
                    fillColor: AppColors.background,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  ),
                ),
                const SizedBox(height: 10),
                OutlinedButton(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.primary,
                    side: const BorderSide(color: AppColors.primary),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  onPressed: _saveUrl,
                  child: const Text('Save URL'),
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // About
          _SectionHeader('About'),
          const SizedBox(height: 8),
          _SettingCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 40, height: 40,
                      decoration: BoxDecoration(
                        color: AppColors.primary.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Center(
                        child: Text('⚡', style: TextStyle(fontSize: 20)),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('OptiGold', style: AppTypography.bodyMedium.copyWith(color: AppColors.primary)),
                        Text('v1.0.0 · GLD Options Advisor', style: AppTypography.metricLabel),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                Text(
                  'For informational purposes only. Not financial advice. Always conduct your own due diligence before trading.',
                  style: AppTypography.metricLabel.copyWith(height: 1.6),
                ),
              ],
            ),
          ),

          const SizedBox(height: 40),
        ],
      ),
    );

    return Platform.isIOS
        ? CupertinoPageScaffold(
            backgroundColor: AppColors.background,
            navigationBar: const CupertinoNavigationBar(
              backgroundColor: AppColors.background,
              border: null,
              middle: Text('Settings'),
            ),
            child: SafeArea(child: body),
          )
        : Scaffold(
            backgroundColor: AppColors.background,
            appBar: AppBar(title: const Text('Settings')),
            body: body,
          );
  }

  Future<void> _saveUrl() async {
    final url = _urlController.text.trim();
    if (url.isEmpty) return;
    await ref.read(sharedPreferencesProvider).setString(AppConstants.baseUrlKey, url);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Server URL saved. Restart app to apply.')),
      );
    }
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }
}

class _ProfileCard extends ConsumerWidget {
  final profile;
  const _ProfileCard({required this.profile});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return _SettingCard(
      child: Column(
        children: [
          _ProfileRow('Capital', '\$${profile.capital.toStringAsFixed(0)}'),
          _ProfileRow('Max Loss / Trade', '\$${profile.maxLossPerTrade.toStringAsFixed(0)}'),
          _ProfileRow('Experience', profile.experienceLevel),
          _ProfileRow('Horizon', profile.timeHorizon),
          _ProfileRow('Risk Multiplier', '${(profile.riskMultiplier * 100).toStringAsFixed(0)}%'),
          _Divider(),
          _ToggleRow(
            label: 'Accepts Options',
            value: profile.acceptsOptions,
            onChanged: (v) => ref.read(profileProvider.notifier).patch({'accepts_options': v}),
          ),
          _ToggleRow(
            label: 'Accepts Margin',
            value: profile.acceptsMargin,
            onChanged: (v) => ref.read(profileProvider.notifier).patch({'accepts_margin': v}),
          ),
          _ToggleRow(
            label: 'Multi-Leg Strategies',
            value: profile.acceptsMultiLeg,
            onChanged: (v) => ref.read(profileProvider.notifier).patch({'accepts_multi_leg': v}),
          ),
          _ToggleRow(
            label: 'Push Notifications',
            value: profile.notificationsEnabled,
            onChanged: (v) => ref.read(profileProvider.notifier).patch({'notifications_enabled': v}),
          ),
        ],
      ),
    );
  }
}

class _ProfileRow extends StatelessWidget {
  final String label;
  final String value;
  const _ProfileRow(this.label, this.value);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          children: [
            Text(label, style: AppTypography.bodyRegular),
            const Spacer(),
            Text(value, style: AppTypography.bodyMedium.copyWith(color: AppColors.primary)),
          ],
        ),
      );
}

class _ToggleRow extends StatelessWidget {
  final String label;
  final bool value;
  final ValueChanged<bool> onChanged;
  const _ToggleRow({required this.label, required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          children: [
            Text(label, style: AppTypography.bodyRegular),
            const Spacer(),
            Platform.isIOS
                ? CupertinoSwitch(value: value, activeColor: AppColors.primary, onChanged: onChanged)
                : Switch(value: value, activeColor: AppColors.primary, onChanged: onChanged),
          ],
        ),
      );
}

class _Divider extends StatelessWidget {
  @override
  Widget build(BuildContext context) => const Divider(
        color: AppColors.divider, height: 20, thickness: 1,
      );
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);
  @override
  Widget build(BuildContext context) => Text(
        title.toUpperCase(),
        style: AppTypography.sectionLabel,
      );
}

class _SettingCard extends StatelessWidget {
  final Widget child;
  const _SettingCard({required this.child});
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.divider),
        ),
        child: child,
      );
}
