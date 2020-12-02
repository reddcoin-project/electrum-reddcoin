package org.electrum_redd.electrum_redd2

import android.graphics.drawable.Drawable
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.content.res.AppCompatResources
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.lifecycle.observe
import com.chaquo.python.Kwarg
import com.chaquo.python.PyObject
import kotlinx.android.synthetic.main.transaction_detail.*
import kotlinx.android.synthetic.main.transactions.*
import kotlin.math.roundToInt


class TransactionsFragment : Fragment(R.layout.transactions), MainFragment {
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        setupVerticalList(rvTransactions)
        rvTransactions.adapter = TransactionsAdapter(activity!!)
        TriggerLiveData().apply {
            addSource(daemonUpdate)
            addSource(settings.getString("base_unit"))
        }.observe(viewLifecycleOwner, { refresh() })

        btnSend.setOnClickListener {
            try {
                showDialog(activity!!, SendDialog())
            } catch (e: ToastException) { e.show() }
        }
        btnRequest.setOnClickListener { newRequest(activity!!) }
    }

    fun refresh() {
        val wallet = daemonModel.wallet
        (rvTransactions.adapter as TransactionsAdapter).submitList(
            if (wallet == null) null else TransactionsList(wallet))
    }
}


class TransactionsList(wallet: PyObject, addr: PyObject? = null)
    : AbstractList<TransactionModel>() {

    val history = wallet.callAttr("get_history",
                                  Kwarg("domain", if (addr == null) null else arrayOf(addr)))
                  .asList()

    override val size by lazy { history.size }

    override fun get(index: Int) = TransactionModel(history.get(size - index - 1))
}


class TransactionsAdapter(val activity: FragmentActivity)
    : BoundAdapter<TransactionModel>(R.layout.transaction_list) {

    override fun onBindViewHolder(holder: BoundViewHolder<TransactionModel>, position: Int) {
        super.onBindViewHolder(holder, position)
        holder.itemView.setOnClickListener {
            val txid = holder.item.txid
            val tx = daemonModel.wallet!!.get("transactions")!!.callAttr("get", txid)
            if (tx == null) {  // Can happen during wallet sync.
                toast(R.string.Transaction_not, Toast.LENGTH_SHORT)
            } else {
                showDialog(activity, TransactionDialog(txid))
            }
        }
    }
}

class TransactionModel(val txHistory: PyObject) {
    private fun get(key: String) = txHistory.get(key)!!

    val txid by lazy { get("tx_hash").toString() }
    val amount by lazy { get("amount").toLong() }
    val balance by lazy { get("balance").toLong() }
    val timestamp by lazy { formatTime(get("timestamp").toLong()) }
    val label by lazy { getDescription(txid) }

    val icon: Drawable by lazy {
        // Support inflation of vector images before API level 21.
        AppCompatResources.getDrawable(
            app,
            if (amount >= 0) R.drawable.ic_add_24dp
            else R.drawable.ic_remove_24dp)!!
    }

    val status: String  by lazy {
        val confirmations = get("conf").toInt()
        when {
            confirmations <= 0 -> app.getString(R.string.unconfirmed)
            else -> app.resources.getQuantityString(R.plurals._1_s,
                                                    confirmations, confirmations)
        }
    }
}


class TransactionDialog() : AlertDialogFragment() {
    constructor(txid: String) : this() {
        arguments = Bundle().apply { putString("txid", txid) }
    }

    val wallet by lazy { daemonModel.wallet!! }
    val txid by lazy { arguments!!.getString("txid")!! }
    val tx by lazy { wallet.get("transactions")!!.callAttr("get", txid)!! }
    val txInfo by lazy { wallet.callAttr("get_tx_info", tx) }

    override fun onBuildDialog(builder: AlertDialog.Builder) {
        builder.setView(R.layout.transaction_detail)
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(android.R.string.ok, {_, _ ->
                setDescription(txid, etDescription.text.toString())
            })
    }

    override fun onShowDialog() {
        btnExplore.setOnClickListener { exploreTransaction(activity!!, txid) }
        btnCopy.setOnClickListener { copyToClipboard(txid, R.string.transaction_id) }

        tvTxid.text = txid

        // For outgoing transactions, the list view includes the fee in the amount, but the
        // detail view does not.
        tvAmount.text = ltr(formatSatoshisAndUnit(txInfo.get("amount")?.toLong(), signed=true))
        tvTimestamp.text = ltr(formatTime(txInfo.get("timestamp")?.toLong()))
        tvStatus.text = txInfo.get("status")!!.toString()

        val size = tx.callAttr("estimated_size").toInt()
        tvSize.text = getString(R.string.bytes, size)

        val fee = txInfo.get("fee")?.toLong()
        if (fee == null) {
            tvFee.text = getString(R.string.Unknown)
        } else {
            val feeSpb = (fee.toDouble() / size.toDouble()).roundToInt()
            tvFee.text = String.format("%s (%s)",
                                       getString(R.string.sat_byte, feeSpb),
                                       ltr(formatSatoshisAndUnit(fee)))
        }
    }

    override fun onFirstShowDialog() {
        etDescription.setText(txInfo.get("label")!!.toString())
    }
}