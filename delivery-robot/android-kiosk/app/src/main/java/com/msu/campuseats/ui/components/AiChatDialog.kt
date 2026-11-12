package com.msu.campuseats.ui.components

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.msu.campuseats.data.BackendRepository
import com.msu.campuseats.data.remote.AiParseOrderResponse
import java.util.Locale
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

private enum class ChatRole { USER, ASSISTANT }

private data class ChatMessage(val role: ChatRole, val text: String)

@Composable
@OptIn(ExperimentalMaterial3Api::class)
fun AiChatBottomSheet(
    onDismiss: () -> Unit,
    vendorNames: Map<Int, String>,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val sessionId = remember { UUID.randomUUID().toString() }
    val messages = remember {
        mutableStateListOf(
            ChatMessage(
                ChatRole.ASSISTANT,
                "Tell me what you would like to order and where it should be delivered."
            )
        )
    }
    val listState = rememberLazyListState()
    val suggestions = remember {
        listOf(
            "One soda delivered to the library",
            "I want a veggie wrap at the Student Center"
        )
    }
    var input by remember { mutableStateOf("") }
    var studentName by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var draft by remember { mutableStateOf<AiParseOrderResponse?>(null) }
    var isBusy by remember { mutableStateOf(false) }
    var orderSubmitted by remember { mutableStateOf(false) }

    val speechIntent = remember {
        Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
            putExtra(RecognizerIntent.EXTRA_PROMPT, "Say your order and delivery location")
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
    }
    val speechLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val transcript = result.data
                ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                ?.firstOrNull()
                .orEmpty()
            if (transcript.isNotBlank()) {
                input = transcript
            } else {
                messages.add(ChatMessage(ChatRole.ASSISTANT, "I did not catch that. Please try speaking again."))
            }
        }
    }
    val launchRecognition: () -> Unit = {
        try {
            speechLauncher.launch(speechIntent)
        } catch (_: ActivityNotFoundException) {
            messages.add(
                ChatMessage(
                    ChatRole.ASSISTANT,
                    "Speech recognition is not available on this device. You can type your order instead."
                )
            )
        }
    }
    val microphonePermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            launchRecognition()
        } else {
            messages.add(
                ChatMessage(ChatRole.ASSISTANT, "Microphone access was denied. You can still type your order.")
            )
        }
    }

    fun startVoiceInput() {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            launchRecognition()
        } else {
            microphonePermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    fun sendMessage(rawText: String) {
        val transcript = rawText.trim()
        if (transcript.isEmpty() || isBusy || orderSubmitted) return

        messages.add(ChatMessage(ChatRole.USER, transcript))
        input = ""
        draft = null
        scope.launch {
            isBusy = true
            try {
                val response = BackendRepository.parseOrderTurn(sessionId, transcript)
                val canConfirm = response.action.equals("CONFIRM", ignoreCase = true) &&
                    response.validForSubmission &&
                    !response.confirmationToken.isNullOrBlank() &&
                    response.vendorId != null &&
                    !response.deliveryLocation.isNullOrBlank() &&
                    response.items.isNotEmpty()
                if (canConfirm) {
                    draft = response
                    messages.add(
                        ChatMessage(
                            ChatRole.ASSISTANT,
                            "I have prepared a draft. Review the items, vendor, and delivery location below before placing it."
                        )
                    )
                } else {
                    val prompt = response.clarificationNeeded?.takeIf { it.isNotBlank() }
                        ?: when (response.action.uppercase(Locale.ROOT)) {
                            "ESCALATE" -> "I could not safely complete this order. Please review it with a staff member."
                            "REPAIR" -> "I need to correct something in the order. Please clarify your request."
                            else -> "I need a little more information. What would you like to change or add?"
                        }
                    messages.add(ChatMessage(ChatRole.ASSISTANT, prompt))
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                messages.add(
                    ChatMessage(
                        ChatRole.ASSISTANT,
                        "I could not reach the ordering service. Please check the connection and try again."
                    )
                )
            } finally {
                isBusy = false
            }
        }
    }

    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    LaunchedEffect(messages.size, draft, isBusy) {
        val lastItem = (listState.layoutInfo.totalItemsCount - 1).coerceAtLeast(0)
        listState.animateScrollToItem(lastItem)
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        modifier = modifier,
        tonalElevation = 4.dp
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.9f)
                .imePadding()
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 14.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text("Campus Eats AI", fontWeight = FontWeight.SemiBold)
                    Text("Order by typing or speaking", style = MaterialTheme.typography.bodySmall)
                }
                IconButton(onClick = onDismiss) {
                    Icon(Icons.Default.Close, contentDescription = "Close")
                }
            }

            Spacer(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(1.dp)
                    .background(MaterialTheme.colorScheme.outlineVariant)
            )

            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                items(messages) { message ->
                    val isUser = message.role == ChatRole.USER
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
                    ) {
                        val bubbleColor = if (isUser) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.surfaceVariant
                        }
                        val textColor = if (isUser) {
                            MaterialTheme.colorScheme.onPrimary
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        }
                        Card(
                            shape = androidx.compose.foundation.shape.RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(containerColor = bubbleColor)
                        ) {
                            Text(
                                text = message.text,
                                color = textColor,
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp)
                            )
                        }
                    }
                }

                if (isBusy) {
                    item(key = "ai-working") {
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                            Text("Understanding your order...", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }

                draft?.let { orderDraft ->
                    item(key = "ai-order-review") {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.secondaryContainer
                            )
                        ) {
                            Column(
                                modifier = Modifier.padding(14.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Text("Review your order", style = MaterialTheme.typography.titleMedium)
                                Text(
                                    "Vendor: " + (orderDraft.vendorId?.let {
                                        vendorNames[it] ?: ("Vendor #" + it)
                                    } ?: "Unavailable"),
                                    style = MaterialTheme.typography.bodyMedium
                                )
                                orderDraft.items.forEach { line ->
                                    Text(line.quantity.toString() + " x " + line.name, fontWeight = FontWeight.Medium)
                                    if (line.customizations.isNotEmpty()) {
                                        Text("Options: " + line.customizations.joinToString())
                                    }
                                }
                                Text("Deliver to: " + orderDraft.deliveryLocation.orEmpty())
                                Text(
                                    "Prices are verified by the backend when the order is placed.",
                                    style = MaterialTheme.typography.bodySmall
                                )
                                OutlinedTextField(
                                    value = studentName,
                                    onValueChange = { studentName = it },
                                    label = { Text("Name (optional)") },
                                    singleLine = true,
                                    modifier = Modifier.fillMaxWidth()
                                )
                                OutlinedTextField(
                                    value = phone,
                                    onValueChange = { phone = it },
                                    label = { Text("Phone") },
                                    singleLine = true,
                                    modifier = Modifier.fillMaxWidth()
                                )
                                OutlinedTextField(
                                    value = email,
                                    onValueChange = { email = it },
                                    label = { Text("Email (alternative)") },
                                    singleLine = true,
                                    modifier = Modifier.fillMaxWidth()
                                )
                                Text("Enter a phone number or email to continue.", style = MaterialTheme.typography.bodySmall)
                                Button(
                                    onClick = {
                                        scope.launch {
                                            isBusy = true
                                            try {
                                                val orderId = BackendRepository.placeAiOrder(
                                                    sessionId = sessionId,
                                                    draft = orderDraft,
                                                    studentName = studentName.trim(),
                                                    phone = phone.trim(),
                                                    email = email.trim()
                                                )
                                                orderSubmitted = true
                                                draft = null
                                                messages.add(
                                                    ChatMessage(
                                                        ChatRole.ASSISTANT,
                                                        "Order #" + orderId + " was placed successfully."
                                                    )
                                                )
                                            } catch (cancelled: CancellationException) {
                                                throw cancelled
                                            } catch (_: Exception) {
                                                messages.add(
                                                    ChatMessage(
                                                        ChatRole.ASSISTANT,
                                                        "The order was not placed. Please review your details and try again."
                                                    )
                                                )
                                            } finally {
                                                isBusy = false
                                            }
                                        }
                                    },
                                    enabled = !isBusy && !orderSubmitted &&
                                        (phone.isNotBlank() || email.isNotBlank()) &&
                                        !orderDraft.confirmationToken.isNullOrBlank(),
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Text(if (isBusy) "Processing..." else "Confirm and place order")
                                }
                            }
                        }
                    }
                }
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                suggestions.forEach { suggestion ->
                    AssistChip(
                        onClick = { sendMessage(suggestion) },
                        enabled = !isBusy && !orderSubmitted,
                        label = { Text(suggestion) }
                    )
                }
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    placeholder = { Text("Type your order...") },
                    modifier = Modifier.weight(1f),
                    maxLines = 3,
                    enabled = !isBusy && !orderSubmitted
                )
                Spacer(modifier = Modifier.width(4.dp))
                IconButton(
                    onClick = { startVoiceInput() },
                    enabled = !isBusy && !orderSubmitted,
                    modifier = Modifier.size(44.dp)
                ) {
                    Icon(Icons.Default.Mic, contentDescription = "Speak your order")
                }
                IconButton(
                    onClick = { sendMessage(input) },
                    enabled = input.isNotBlank() && !isBusy && !orderSubmitted,
                    modifier = Modifier.size(44.dp)
                ) {
                    Icon(
                        Icons.Default.Send,
                        contentDescription = "Send order text",
                        tint = MaterialTheme.colorScheme.primary
                    )
                }
            }
            Text(
                "The system speech service transcribes your voice; only the text is sent to campus AI.",
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 8.dp),
                style = MaterialTheme.typography.bodySmall
            )
        }
    }
}
