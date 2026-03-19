import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api/models/position.dart';
import '../../core/theme/colors.dart';
import '../../core/theme/typography.dart';
import '../../core/utils/formatters.dart';
import '../../providers/position_provider.dart';
import '../../widgets/loading_shimmer.dart';

class PositionsScreen extends ConsumerStatefulWidget {
  const PositionsScreen({super.key});

  @override
  ConsumerState<PositionsScreen> createState() => _PositionsScreenState();
}

class _PositionsScreenState extends ConsumerState<PositionsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabs;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final posAsync = ref.watch(positionsProvider);

    final tabBar = TabBar(
      controller: _tabs,
      indicatorColor: AppColors.primary,
      labelColor: AppColors.primary,
      unselectedLabelColor: AppColors.textMuted,
      tabs: const [Tab(text: 'Open'), Tab(text: 'Closed')],
    );

    final body = posAsync.when(
      data: (positions) => TabBarView(
        controller: _tabs,
        children: [
          _PositionList(
            positions: positions.where((p) => p.isOpen).toList(),
            onClose: (p) => _showCloseSheet(context, p),
          ),
          _PositionList(
            positions: positions.where((p) => p.isClosed).toList(),
            onClose: null,
          ),
        ],
      ),
      loading: () => const Center(child: CircularProgressIndicator(color: AppColors.primary)),
      error: (e, _) => Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.wifi_off, color: AppColors.textMuted, size: 40),
            const SizedBox(height: 12),
            Text('Could not load positions', style: AppTypography.bodyMedium),
            Text('Make sure the backend is running', style: AppTypography.bodyRegular),
          ],
        ),
      ),
    );

    return Platform.isIOS
        ? CupertinoPageScaffold(
            backgroundColor: AppColors.background,
            navigationBar: const CupertinoNavigationBar(
              backgroundColor: AppColors.background,
              border: null,
              middle: Text('Positions'),
            ),
            child: Column(
              children: [
                const SizedBox(height: 88),
                tabBar,
                Expanded(child: body),
              ],
            ),
          )
        : Scaffold(
            backgroundColor: AppColors.background,
            appBar: AppBar(
              title: const Text('Positions'),
              bottom: PreferredSize(preferredSize: const Size.fromHeight(48), child: tabBar),
            ),
            body: body,
          );
  }

  Future<void> _showCloseSheet(BuildContext context, PositionModel pos) async {
    final priceCtrl = TextEditingController();
    String? selectedReason;

    const reasons = [
      ('profit_target', 'Profit Target (50%)'),
      ('stop_loss',     'Stop Loss'),
      ('21dte',         '21 DTE Rule'),
      ('expiry',        'Expiry'),
      ('manual',        'Manual Close'),
    ];

    await showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => Padding(
          padding: EdgeInsets.only(
            left: 24, right: 24, top: 20,
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 24,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Handle bar
              Center(
                child: Container(
                  width: 40, height: 4,
                  decoration: BoxDecoration(
                    color: AppColors.divider,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Text('Close Position', style: AppTypography.strategyName),
              Text(pos.formattedStrategy, style: AppTypography.bodyRegular),
              const SizedBox(height: 20),

              // Close price input
              TextField(
                controller: priceCtrl,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                style: const TextStyle(color: AppColors.textPrimary),
                decoration: InputDecoration(
                  labelText: 'Close Price',
                  labelStyle: const TextStyle(color: AppColors.textSecondary),
                  prefixText: '\$',
                  prefixStyle: TextStyle(color: AppColors.gold),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: AppColors.divider),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: AppColors.primary),
                  ),
                  filled: true,
                  fillColor: AppColors.background,
                ),
              ),
              const SizedBox(height: 16),

              // Exit reason
              Text('Exit Reason', style: AppTypography.metricLabel),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: reasons.map((r) {
                  final (code, label) = r;
                  final selected = selectedReason == code;
                  return ChoiceChip(
                    label: Text(label,
                        style: AppTypography.chipLabel.copyWith(
                          color: selected ? Colors.white : AppColors.textSecondary,
                          fontSize: 11,
                        )),
                    selected: selected,
                    selectedColor: AppColors.primary,
                    backgroundColor: AppColors.background,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                      side: BorderSide(
                        color: selected ? AppColors.primary : AppColors.divider,
                      ),
                    ),
                    onSelected: (_) => setState(() => selectedReason = code),
                  );
                }).toList(),
              ),
              const SizedBox(height: 20),

              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: () async {
                    final price = double.tryParse(priceCtrl.text);
                    if (price == null) return;
                    Navigator.pop(ctx);
                    await ref.read(positionsProvider.notifier).close(
                      pos.id, price,
                      closeReason: selectedReason,
                    );
                  },
                  child: const Text('Confirm Close'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PositionList extends StatelessWidget {
  final List<PositionModel> positions;
  final Function(PositionModel)? onClose;
  const _PositionList({required this.positions, this.onClose});

  @override
  Widget build(BuildContext context) {
    if (positions.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('📁', style: TextStyle(fontSize: 48)),
            const SizedBox(height: 16),
            Text('No positions', style: AppTypography.bodyMedium),
            Text('Execute a trade from Signal Detail',
                style: AppTypography.bodyRegular),
          ],
        ),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: positions.length,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (_, i) => _PositionCard(
        position: positions[i],
        index: i,
        onClose: onClose != null ? () => onClose!(positions[i]) : null,
      ),
    );
  }
}

class _PositionCard extends StatelessWidget {
  final PositionModel position;
  final int index;
  final VoidCallback? onClose;
  const _PositionCard({required this.position, required this.index, this.onClose});

  @override
  Widget build(BuildContext context) {
    final pnl     = position.realizedPnl;
    final isProfit = (pnl ?? 0) >= 0;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: position.isClosed
              ? (isProfit ? AppColors.profit.withOpacity(0.3) : AppColors.loss.withOpacity(0.3))
              : AppColors.divider,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: position.isOpen
                      ? AppColors.primary.withOpacity(0.1)
                      : AppColors.divider,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  position.isOpen ? 'OPEN' : 'CLOSED',
                  style: AppTypography.chipLabel.copyWith(
                    color: position.isOpen ? AppColors.primary : AppColors.textMuted,
                    fontSize: 9,
                  ),
                ),
              ),
              const Spacer(),
              if (pnl != null)
                Text(
                  '${isProfit ? "+" : ""}${Fmt.currency(pnl)}',
                  style: AppTypography.metricValue.copyWith(
                    color: isProfit ? AppColors.profit : AppColors.loss,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 10),
          Text(position.formattedStrategy, style: AppTypography.bodyMedium),
          const SizedBox(height: 4),
          Row(
            children: [
              if (position.strikeA != null)
                Text('Strike: ${Fmt.currency(position.strikeA)}',
                    style: AppTypography.metricLabel),
              if (position.expiry != null) ...[
                const Text(' · ', style: TextStyle(color: AppColors.textMuted, fontSize: 10)),
                Text('Exp: ${Fmt.dateShort(position.expiry)}',
                    style: AppTypography.metricLabel),
              ],
              if (position.quantity != null) ...[
                const Text(' · ', style: TextStyle(color: AppColors.textMuted, fontSize: 10)),
                Text('${position.quantity}x', style: AppTypography.metricLabel),
              ],
            ],
          ),
          // DTE display + 21-DTE warning
          if (position.isOpen && position.expiry != null) ...[
            const SizedBox(height: 8),
            _DteWarning(expiry: position.expiry!),
          ],
          if (position.isOpen && onClose != null) ...[
            const SizedBox(height: 14),
            OutlinedButton(
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.primary,
                side: const BorderSide(color: AppColors.primary),
                minimumSize: const Size.fromHeight(40),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              onPressed: onClose,
              child: const Text('Close Position'),
            ),
          ],
        ],
      ),
    ).animate().fadeIn(delay: (index * 50).ms).slideY(begin: 0.05, end: 0);
  }
}

class _DteWarning extends StatelessWidget {
  final String expiry;
  const _DteWarning({required this.expiry});

  @override
  Widget build(BuildContext context) {
    final expiryDate = DateTime.tryParse(expiry);
    if (expiryDate == null) return const SizedBox.shrink();
    final dte = expiryDate.difference(DateTime.now()).inDays;
    final label = 'DTE: $dte day${dte == 1 ? '' : 's'}';

    if (dte <= 21) {
      return Row(
        children: [
          const Icon(Icons.warning_amber_rounded, size: 14, color: Colors.orange),
          const SizedBox(width: 4),
          Text(
            '$label — consider closing (21 DTE rule)',
            style: AppTypography.metricLabel.copyWith(color: Colors.orange, fontSize: 11),
          ),
        ],
      );
    }

    return Text(label, style: AppTypography.metricLabel.copyWith(fontSize: 11));
  }
}
