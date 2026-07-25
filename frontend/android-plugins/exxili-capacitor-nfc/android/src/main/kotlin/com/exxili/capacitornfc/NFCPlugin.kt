package com.exxili.capacitornfc

import android.app.ActivityOptions
import android.app.PendingIntent
import android.content.Intent
import android.content.IntentFilter
import android.nfc.NdefMessage
import android.nfc.NdefRecord
import android.nfc.NfcAdapter
import android.nfc.NfcAdapter.ACTION_NDEF_DISCOVERED
import android.nfc.NfcAdapter.ACTION_TAG_DISCOVERED
import android.nfc.NfcAdapter.ACTION_TECH_DISCOVERED
import android.nfc.NfcAdapter.EXTRA_NDEF_MESSAGES
import android.nfc.NfcAdapter.getDefaultAdapter
import android.nfc.Tag
import android.nfc.tech.IsoDep
import android.nfc.tech.MifareClassic
import android.nfc.tech.MifareUltralight
import android.nfc.tech.Ndef
import android.nfc.tech.NdefFormatable
import android.nfc.tech.NfcA
import android.nfc.tech.NfcB
import android.nfc.tech.NfcBarcode
import android.nfc.tech.NfcF
import android.nfc.tech.NfcV
import android.os.Build
import android.os.Bundle
import android.util.Log
import androidx.annotation.RequiresApi
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import org.json.JSONObject
import java.io.IOException
import java.io.UnsupportedEncodingException
import java.nio.charset.Charset
import java.util.Base64
import kotlin.math.min

@CapacitorPlugin(name = "NFC")
class NFCPlugin : Plugin() {
    private var writeMode = false
    private var recordsBuffer: JSArray? = null

    private val techListsArray = arrayOf(arrayOf<String>(
        IsoDep::class.java.name,
        MifareClassic::class.java.name,
        MifareUltralight::class.java.name,
        Ndef::class.java.name,
        NdefFormatable::class.java.name,
        NfcBarcode::class.java.name,
        NfcA::class.java.name,
        NfcB::class.java.name,
        NfcF::class.java.name,
        NfcV::class.java.name
    ))

    @RequiresApi(Build.VERSION_CODES.TIRAMISU)
    public override fun handleOnNewIntent(intent: Intent?) {
        super.handleOnNewIntent(intent)

        if (intent == null || intent.action.isNullOrBlank()) {
            return
        }

        if (writeMode) {
            Log.d("NFC", "WRITE MODE START")
            handleWriteTag(intent)
            writeMode = false
            recordsBuffer = null
        }
    else if (ACTION_NDEF_DISCOVERED == intent.action || ACTION_TAG_DISCOVERED == intent.action || ACTION_TECH_DISCOVERED == intent.action) {
            Log.d("NFC", "READ MODE START")
            handleReadTag(intent)
        }
    }

    @PluginMethod
    fun isSupported(call: PluginCall) {
        val adapter = NfcAdapter.getDefaultAdapter(this.activity)
        val ret = JSObject()
        ret.put("supported", adapter != null)
        call.resolve(ret)
    }

    @PluginMethod
    fun cancelWriteAndroid(call: PluginCall) {
        this.writeMode = false
        call.resolve()
    }

    @PluginMethod
    fun startScan(call: PluginCall) {
        print("startScan called")
        call.reject("Android NFC scanning does not require 'startScan' method.")
    }

    @PluginMethod
    fun writeNDEF(call: PluginCall) {
        print("writeNDEF called")

        writeMode = true
        recordsBuffer = call.getArray("records")

        call.resolve()
    }

    override fun handleOnPause() {
        super.handleOnPause()
        getDefaultAdapter(this.activity)?.disableForegroundDispatch(this.activity)
    }

    override fun handleOnResume() {
        super.handleOnResume()
        if(getDefaultAdapter(this.activity) == null) return;

        val intent = Intent(context, this.activity.javaClass).apply {
            addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
        }

        val pendingIntentFlags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            PendingIntent.FLAG_MUTABLE
        } else {
            PendingIntent.FLAG_UPDATE_CURRENT
        }

        var activityOptionsBundle: Bundle? = null

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) { // API 35 (Android 15)
            activityOptionsBundle = ActivityOptions.makeBasic().apply {
                setPendingIntentCreatorBackgroundActivityStartMode(ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED)
            }.toBundle()
        }

        val pendingIntent =
            PendingIntent.getActivity(
                this.activity,
                0,
                intent,
                pendingIntentFlags,
                activityOptionsBundle
            )

        val intentFilter: Array<IntentFilter> =
            arrayOf(
                IntentFilter(ACTION_NDEF_DISCOVERED).apply {
                    try {
                        addDataType("text/plain")
                    } catch (e: IntentFilter.MalformedMimeTypeException) {
                        throw RuntimeException("failed", e)
                    }
                },
                IntentFilter(ACTION_TECH_DISCOVERED),
                IntentFilter(ACTION_TAG_DISCOVERED)
            )

        getDefaultAdapter(this.activity).enableForegroundDispatch(
            this.activity,
            pendingIntent,
            intentFilter,
            techListsArray
        )
    }

    @RequiresApi(Build.VERSION_CODES.TIRAMISU)
    private fun handleWriteTag(intent: Intent) {
        val records = recordsBuffer?.toList<JSONObject>()
        if(records != null) {
            val ndefRecords = mutableListOf<NdefRecord>()

            try {
                for (record in records) {
                    val payload = record.getJSONArray("payload")
                    val type: String? = record.getString("type")

                    if (payload.length() == 0 || type == null) {
                        notifyListeners(
                            "nfcError",
                            JSObject().put(
                                "error",
                                "Invalid record: payload or type is missing."
                            )
                        )
                        return
                    }

                    val payloadBytes = ByteArray(payload.length())
                    for(i in 0 until payload.length()) {
                        payloadBytes[i] = payload.getInt(i).toByte()
                    }

                    val (tnf, typeBytes) = when {
                        type == "T" || type == "U" -> Pair(
                            NdefRecord.TNF_WELL_KNOWN,
                            type.toByteArray(Charsets.UTF_8)
                        )
                        type.contains("/") -> Pair(
                            NdefRecord.TNF_MIME_MEDIA,
                            type.toByteArray(Charsets.US_ASCII)
                        )
                        else -> Pair(
                            NdefRecord.TNF_EXTERNAL_TYPE,
                            type.toByteArray(Charsets.UTF_8)
                        )
                    }

                    val record = if (tnf == NdefRecord.TNF_MIME_MEDIA) {
                        try {
                            NdefRecord.createMime(type, payloadBytes)
                        } catch (e: IllegalArgumentException) {
                            notifyListeners(
                                "nfcError",
                                JSObject().put(
                                    "error",
                                    "Invalid MIME type for record"
                                )
                            )
                            return
                        }
                    } else {
                        NdefRecord(
                            tnf,
                            typeBytes,
                            ByteArray(0),
                            payloadBytes
                        )
                    }

                    ndefRecords.add(record)
                }

                val ndefMessage = NdefMessage(ndefRecords.toTypedArray())
                val tag = intent.getParcelableExtra(NfcAdapter.EXTRA_TAG, Tag::class.java)
                var ndef = Ndef.get(tag)
                val tagSummary = describeTag(tag)
                val messageSize = ndefMessage.toByteArray().size

                if (ndef == null) {
                    val formatable = NdefFormatable.get(tag)
                    if (formatable != null) {
                        var primaryFormatError: Throwable? = null
                        try {
                            Log.d("NFC", "Formatting blank NFC tag before write. ${tagSummary}; messageSize=${messageSize}")
                            formatable.connect()
                            formatable.format(ndefMessage)
                            Log.d("NFC", "NDEF message successfully formatted and written to blank tag.")
                            notifyListeners("nfcWriteSuccess", JSObject().put("success", true))
                            return
                        } catch (e: IOException) {
                            primaryFormatError = e
                            Log.e("NFC", "Error formatting NDEF-formatable tag. ${tagSummary}; messageSize=${messageSize}", e)
                        } catch (e: Exception) {
                            primaryFormatError = e
                            Log.e("NFC", "Error during NDEF formatting. ${tagSummary}; messageSize=${messageSize}", e)
                        } finally {
                            try {
                                formatable.close()
                            } catch (e: IOException) {
                                Log.w("NFC", "Error closing NdefFormatable connection: ${e.message}")
                            }
                        }

                        try {
                            Log.w("NFC", "Falling back to manual Type 2 formatting. ${tagSummary}; messageSize=${messageSize}")
                            writeType2TagFallback(tag, ndefMessage)
                            Log.d("NFC", "Manual Type 2 formatting fallback succeeded.")
                            notifyListeners("nfcWriteSuccess", JSObject().put("success", true).put("fallback", "type2_manual"))
                            return
                        } catch (fallbackError: Exception) {
                            Log.e("NFC", "Manual Type 2 formatting fallback failed. ${tagSummary}; messageSize=${messageSize}", fallbackError)
                            val primarySummary =
                                if (primaryFormatError == null) {
                                    "primary=none"
                                } else {
                                    "primary=${primaryFormatError.javaClass.simpleName}:${primaryFormatError.message ?: "no message"}"
                                }
                            notifyListeners(
                                "nfcError",
                                JSObject().put(
                                    "error",
                                    "Failed to format and write blank NFC tag (${fallbackError.javaClass.simpleName}): ${fallbackError.message ?: "no message"}. ${primarySummary}; ${tagSummary}; messageSize=${messageSize}"
                                )
                            )
                            return
                        }
                    } else {
                        notifyListeners(
                            "nfcError",
                            JSObject().put(
                                "error",
                                "Tag does not support NDEF writing."
                            )
                        )
                        return
                    }
                }

                ndef.use { connectedNdef ->
                    Log.d("NFC", "Writing NDEF message to existing formatted tag. ${tagSummary}; messageSize=${messageSize}")
                    connectedNdef.connect()
                    if (!connectedNdef.isWritable) {
                        notifyListeners(
                            "nfcError",
                            JSObject().put(
                                "error",
                                "NFC tag is not writable. ${tagSummary}"
                            )
                        )
                        return
                    }
                    if (connectedNdef.maxSize < ndefMessage.toByteArray().size) {
                        notifyListeners(
                            "nfcError",
                            JSObject().put(
                                "error",
                                "Message too large for this NFC Tag (max ${connectedNdef.maxSize} bytes). ${tagSummary}"
                            )
                        )
                        return
                    }

                    connectedNdef.writeNdefMessage(ndefMessage)
                    Log.d("NFC", "NDEF message successfully written to tag.")
                }

                notifyListeners("nfcWriteSuccess", JSObject().put("success", true))
            }
            catch (e: UnsupportedEncodingException) {
                Log.e("NFC", "Encoding error during NDEF record creation: ${e.message}")
                notifyListeners(
                    "nfcError",
                    JSObject().put(
                        "error",
                        "Encoding error (${e.javaClass.simpleName}): ${e.message ?: "no message"}"
                    )
                )
            }
            catch (e: IOException) {
                Log.e("NFC", "I/O error during NFC write: ${e.message}")
                notifyListeners(
                    "nfcError",
                    JSObject().put(
                        "error",
                        "NFC I/O error (${e.javaClass.simpleName}): ${e.message ?: "no message"}"
                    )
                )
            }
            catch (e: Exception) {
                Log.e("NFC", "Error writing NDEF message: ${e.message}", e)
                notifyListeners(
                    "nfcError",
                    JSObject().put(
                        "error",
                        "Failed to write NDEF message (${e.javaClass.simpleName}): ${e.message ?: "no message"}"
                    )
                )
            }
        }
        else {
            notifyListeners("nfcError", JSObject().put("error", "Failed to write NFC tag"))
        }
    }

    @RequiresApi(Build.VERSION_CODES.TIRAMISU)
    private fun handleReadTag(intent: Intent) {
        val jsResponse = JSObject()
        val ndefMessages = JSArray()

        // Get tag information regardless of NDEF content
        val tag: Tag? = intent.getParcelableExtra(NfcAdapter.EXTRA_TAG, Tag::class.java)
        val tagInfo = tag?.let { extractTagInfo(it) }

        // Try to obtain raw NDEF messages first (ACTION_NDEF_DISCOVERED path)
        val receivedMessages = intent.getParcelableArrayExtra(
            EXTRA_NDEF_MESSAGES,
            NdefMessage::class.java
        )

        if (receivedMessages != null && receivedMessages.isNotEmpty()) {
            // Standard NDEF-discovered path
            for (message in receivedMessages) {
                ndefMessages.put(ndefMessageToJS(message))
            }
        } else {
            // For ACTION_TAG_DISCOVERED or ACTION_TECH_DISCOVERED we may still have an NDEF tag.
            var added = false
            if (tag != null) {
                val ndef = Ndef.get(tag)
                if (ndef != null) {
                    try {
                        ndef.connect()
                        // Prefer cached message to avoid additional IO if available
                        val message: NdefMessage? = ndef.cachedNdefMessage ?: try {
                            ndef.ndefMessage
                        } catch (e: Exception) { null }
                        if (message != null) {
                            ndefMessages.put(ndefMessageToJS(message))
                            added = true
                        }
                    } catch (e: Exception) {
                        Log.w("NFC", "Failed to read NDEF message from TECH/TAG intent: ${e.message}")
                    } finally {
                        try { ndef.close() } catch (_: Exception) {}
                    }
                }

                // If no NDEF message found, fallback to tag ID (legacy behavior)
                if (!added) {
                    val tagId = intent.getByteArrayExtra(NfcAdapter.EXTRA_ID) ?: tag.id
                    val result = if (tagId != null) byteArrayToHexString(tagId) else ""
                    val rec = JSObject()
                    rec.put("type", "ID")
                    rec.put("payload", Base64.getEncoder().encodeToString(result.toByteArray()))
                    val ndefRecords = JSArray().apply { put(rec) }
                    val msg = JSObject().apply { put("records", ndefRecords) }
                    ndefMessages.put(msg)
                }
            }
        }

        jsResponse.put("messages", ndefMessages)
        // Always include tag information if available
        if (tagInfo != null) {
            jsResponse.put("tagInfo", tagInfo)
        }
        this.notifyListeners("nfcTag", jsResponse)
    }

    private fun extractTagInfo(tag: Tag): JSObject {
        val tagInfo = JSObject()
        
        // Always include UID
        val uid = byteArrayToHexString(tag.id)
        tagInfo.put("uid", uid)
        
        // Include technology types
        val techTypes = JSArray()
        for (tech in tag.techList) {
            techTypes.put(tech)
        }
        tagInfo.put("techTypes", techTypes)
        
        // Try to get NDEF-specific information
        val ndef = Ndef.get(tag)
        if (ndef != null) {
            try {
                ndef.connect()
                tagInfo.put("maxSize", ndef.maxSize)
                tagInfo.put("isWritable", ndef.isWritable)
                tagInfo.put("type", ndef.type)
            } catch (e: Exception) {
                Log.w("NFC", "Failed to read NDEF tag info: ${e.message}")
            } finally {
                try { ndef.close() } catch (_: Exception) {}
            }
        }
        
        return tagInfo
    }

    private fun writeType2TagFallback(tag: Tag?, ndefMessage: NdefMessage) {
        if (tag == null) {
            throw IOException("Tag was null during Type 2 fallback")
        }

        val mifare = MifareUltralight.get(tag)
            ?: throw IOException("MifareUltralight technology not available for Type 2 fallback")
        val nfca = NfcA.get(tag)
            ?: throw IOException("NfcA technology not available for Type 2 fallback")

        val tagType = mifare.type
        val sizeField = when (tagType) {
            MifareUltralight.TYPE_ULTRALIGHT_C -> 0x12
            else -> 0x06
        }
        val capacityBytes = sizeField * 8
        val messageBytes = ndefMessage.toByteArray()
        val tlvBytes = buildType2NdefTlv(messageBytes)
        if (tlvBytes.size > capacityBytes) {
            throw IOException("NDEF TLV is ${tlvBytes.size} bytes but blank tag capacity is ${capacityBytes} bytes")
        }

        Log.d(
            "NFC",
            "Type 2 fallback starting. uid=${byteArrayToHexString(tag.id)}; mifareType=${describeUltralightType(tagType)}; " +
                "capacityBytes=${capacityBytes}; ndefBytes=${messageBytes.size}; tlvBytes=${tlvBytes.size}"
        )

        nfca.connect()
        try {
            writeType2Page(nfca, 3, byteArrayOf(0xE1.toByte(), 0x10, sizeField.toByte(), 0x00))

            // Initialize an empty NDEF TLV first. Some devices/tags reject a direct full-message format.
            writeType2Page(nfca, 4, byteArrayOf(0x03, 0x00, 0xFE.toByte(), 0x00))

            var page = 4
            var offset = 0
            while (offset < tlvBytes.size) {
                val chunk = ByteArray(4)
                val length = min(4, tlvBytes.size - offset)
                System.arraycopy(tlvBytes, offset, chunk, 0, length)
                writeType2Page(nfca, page, chunk)
                page += 1
                offset += 4
            }

            Log.d("NFC", "Type 2 fallback page writes completed. ${readType2Preview(nfca)}")
        } finally {
            try {
                nfca.close()
            } catch (_: Exception) {}
        }

        // The Tag object reflects technologies at discovery time. After manual Type 2 initialization
        // a re-scan may be required before Android exposes Ndef on a freshly formatted blank tag.
        Log.d(
            "NFC",
            "Type 2 fallback completed without immediate NDEF rebind. A fresh scan should now expose the tag as NDEF."
        )
    }

    private fun buildType2NdefTlv(messageBytes: ByteArray): ByteArray {
        val tlv = ArrayList<Byte>()
        tlv.add(0x03)
        if (messageBytes.size < 0xFF) {
            tlv.add(messageBytes.size.toByte())
        } else {
            tlv.add(0xFF.toByte())
            tlv.add(((messageBytes.size shr 8) and 0xFF).toByte())
            tlv.add((messageBytes.size and 0xFF).toByte())
        }
        for (value in messageBytes) {
            tlv.add(value)
        }
        tlv.add(0xFE.toByte())
        while (tlv.size % 4 != 0) {
            tlv.add(0x00)
        }
        return tlv.toByteArray()
    }

    private fun writeType2Page(nfca: NfcA, page: Int, data: ByteArray) {
        if (data.size != 4) {
            throw IOException("Type 2 page writes require exactly 4 bytes, got ${data.size}")
        }
        Log.d("NFC", "Type 2 write page=${page} data=${byteArrayToHexString(data)}")
        nfca.transceive(
            byteArrayOf(
                0xA2.toByte(),
                (page and 0xFF).toByte(),
                data[0],
                data[1],
                data[2],
                data[3]
            )
        )
    }

    private fun readType2Preview(nfca: NfcA): String {
        return try {
            val preview = nfca.transceive(byteArrayOf(0x30, 0x03))
            "previewPages3to6=${byteArrayToHexString(preview)}"
        } catch (e: Exception) {
            "previewReadFailed=${e.javaClass.simpleName}:${e.message ?: "no message"}"
        }
    }

    private fun describeUltralightType(tagType: Int): String {
        return when (tagType) {
            MifareUltralight.TYPE_ULTRALIGHT -> "ultralight"
            MifareUltralight.TYPE_ULTRALIGHT_C -> "ultralight_c"
            MifareUltralight.TYPE_UNKNOWN -> "unknown"
            else -> "other(${tagType})"
        }
    }

    private fun describeTag(tag: Tag?): String {
        if (tag == null) {
            return "tag=null"
        }

        val uid = byteArrayToHexString(tag.id)
        val techList = tag.techList.joinToString(",")
        val ndef = Ndef.get(tag)
        if (ndef != null) {
            return try {
                ndef.connect()
                "uid=${uid}; techs=[${techList}]; ndefType=${ndef.type}; maxSize=${ndef.maxSize}; writable=${ndef.isWritable}"
            } catch (e: Exception) {
                "uid=${uid}; techs=[${techList}]; ndefInfoError=${e.javaClass.simpleName}:${e.message ?: "no message"}"
            } finally {
                try {
                    ndef.close()
                } catch (_: Exception) {}
            }
        }

        val formatable = NdefFormatable.get(tag)
        return "uid=${uid}; techs=[${techList}]; formatable=${formatable != null}"
    }

    private fun ndefMessageToJS(message: NdefMessage): JSObject {
        val ndefRecords = JSArray()
        for (record in message.records) {
            val rec = JSObject()
            rec.put("type", String(record.type, Charsets.UTF_8))
            rec.put("payload", Base64.getEncoder().encodeToString(record.payload))
            ndefRecords.put(rec)
        }
        val msg = JSObject()
        msg.put("records", ndefRecords)
        return msg
    }

    private fun byteArrayToHexString(inarray: ByteArray): String {
        val hex = arrayOf("0","1","2","3","4","5","6","7","8","9","A","B","C","D","E","F")
        var out = ""

        for (j in inarray.indices) {
            val `in` = inarray[j].toInt() and 0xff
            val i1 = (`in` shr 4) and 0x0f
            out += hex[i1]
            val i2 = `in` and 0x0f
            out += hex[i2]
        }
        return out
    }
}
