package com.msu.campuseats.ui.assistant

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.msu.campuseats.data.remote.AiCart
import com.msu.campuseats.data.remote.AiOption
import com.msu.campuseats.ui.theme.kioskScale
import java.util.Locale

private val STARTER_REQUESTS = listOf(
    "One soda delivered to the Student Center",
    "I want a veggie wrap at University Hall"
)

/**
 * The conversational ordering screen: chat, tap-to-answer options, and a cart card
 * with Confirm and Edit. [onUseTouchMenu] leaves for the touch menu, carrying the
 * assistant's cart when it has one; it is always reachable from the top bar and is
 * offered in the chat whenever the assistant fails.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun AssistantScreen(
    onBack: () -> Unit,
    onUseTouchMenu: (AiCart?) -> Unit,
    onOrderPlaced: () -> Unit,
    viewModel: AssistantViewModel = viewModel()
) {
    val state by viewModel.state.collectAsState()
    val scale = kioskScale()
    val listState = rememberLazyListState()
    var input by rememberSaveable { mutableStateOf("") }
    var voiceNotice by remember { mutableStateOf<String?>(null) }
    val startVoiceInput = rememberVoiceInput(
        onTranscript = { input = it; voiceNotice = null },
        onProblem = { voiceNotice = it }
    )
    val orderPlaced = state.placedOrderId != null
    val inputEnabled = !state.isBusy && !orderPlaced

    LaunchedEffect(state.messages.size, state.cart, state.isBusy, state.offerTouchMenu) {
        val lastItem = (listState.layoutInfo.totalItemsCount - 1).coerceAtLeast(0)
        listState.animateScrollToItem(lastItem)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Order with the assistant")
                        Text("Type, speak, or tap an answer", style = MaterialTheme.typography.labelMedium)
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    if (!orderPlaced) {
                        TextButton(onClick = { onUseTouchMenu(state.cart) }) { Text("Use menu") }
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .imePadding()
        ) {
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = (16 * scale).dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                items(state.messages) { message -> MessageBubble(message) }

                if (state.isBusy) {
                    item(key = "assistant-working") {
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                            Text("Working on your order...", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }

                val cart = state.cart
                if (cart != null && state.hasCartItems && !orderPlaced) {
                    item(key = "assistant-cart") {
                        AiCartCard(
                            cart = cart,
                            canConfirm = state.canConfirm,
                            isBusy = state.isBusy,
                            onEditLine = viewModel::editLine,
                            onConfirm = viewModel::confirm
                        )
                    }
                }

                if (state.offerTouchMenu && !orderPlaced) {
                    item(key = "assistant-fallback") {
                        TouchMenuFallback(
                            cart = state.cart,
                            onUseTouchMenu = { onUseTouchMenu(state.cart) }
                        )
                    }
                }

                if (orderPlaced) {
                    item(key = "assistant-done") {
                        Button(
                            onClick = onOrderPlaced,
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 56.dp)
                        ) { Text("Done") }
                    }
                }
            }

            val chips = when {
                !inputEnabled -> emptyList()
                state.options.isNotEmpty() -> state.options
                else -> emptyList()
            }
            val showStarters = inputEnabled && state.options.isEmpty() && state.messages.size == 1
            if (chips.isNotEmpty() || showStarters) {
                FlowRow(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = (16 * scale).dp, vertical = 6.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    chips.forEach { option ->
                        OptionChip(label = option.label, onClick = { viewModel.selectOption(option) })
                    }
                    if (showStarters) {
                        STARTER_REQUESTS.forEach { request ->
                            OptionChip(label = request, onClick = { viewModel.send(request) })
                        }
                    }
                }
            }

            voiceNotice?.let {
                Text(
                    it,
                    modifier = Modifier.padding(horizontal = (16 * scale).dp),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error
                )
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding((12 * scale).dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    placeholder = { Text(if (state.options.isEmpty()) "Type your order..." else "Or type your answer...") },
                    modifier = Modifier.weight(1f),
                    maxLines = 3,
                    enabled = inputEnabled
                )
                IconButton(
                    onClick = startVoiceInput,
                    enabled = inputEnabled,
                    modifier = Modifier.size(56.dp)
                ) {
                    Icon(Icons.Default.Mic, contentDescription = "Speak your order")
                }
                IconButton(
                    onClick = {
                        viewModel.send(input)
                        input = ""
                    },
                    enabled = inputEnabled && input.isNotBlank(),
                    modifier = Modifier.size(56.dp)
                ) {
                    Icon(
                        Icons.Default.Send,
                        contentDescription = "Send",
                        tint = MaterialTheme.colorScheme.primary
                    )
                }
            }
        }
    }
}

@Composable
private fun MessageBubble(message: ChatMessage) {
    val isUser = message.role == ChatRole.USER
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Card(
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(
                containerColor = if (isUser) MaterialTheme.colorScheme.primary
                else MaterialTheme.colorScheme.surfaceVariant
            )
        ) {
            Text(
                text = message.text,
                color = if (isUser) MaterialTheme.colorScheme.onPrimary
                else MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)
            )
        }
    }
}

/** A chip sized for a kiosk touchscreen rather than a phone. */
@Composable
private fun OptionChip(label: String, onClick: () -> Unit) {
    FilledTonalButton(
        onClick = onClick,
        modifier = Modifier.heightIn(min = 56.dp),
        shape = RoundedCornerShape(16.dp)
    ) {
        Text(label)
    }
}

@Composable
private fun TouchMenuFallback(cart: AiCart?, onUseTouchMenu: () -> Unit) {
    val lines = cart?.lines.orEmpty()
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                if (lines.isEmpty()) "You can order from the menu instead."
                else "You can finish this order from the menu. Your items come with you.",
                color = MaterialTheme.colorScheme.onErrorContainer
            )
            if (lines.any { !it.customization.isNullOrBlank() }) {
                Text(
                    "Options such as size or extras are not carried over.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onErrorContainer
                )
            }
            Button(
                onClick = onUseTouchMenu,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 56.dp)
            ) { Text("Order from the menu") }
        }
    }
}

/**
 * Returns a function that starts the system speech recognizer. Only the recognized
 * text reaches the app; it lands in the input field so the customer can correct it.
 */
@Composable
private fun rememberVoiceInput(
    onTranscript: (String) -> Unit,
    onProblem: (String) -> Unit
): () -> Unit {
    val context = LocalContext.current
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
            if (transcript.isNotBlank()) onTranscript(transcript)
            else onProblem("I did not catch that. Please try speaking again.")
        }
    }
    val launchRecognition = {
        try {
            speechLauncher.launch(speechIntent)
        } catch (_: ActivityNotFoundException) {
            onProblem("Speech recognition is not available on this device. Please type instead.")
        }
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) launchRecognition()
        else onProblem("Microphone access was denied. You can still type your order.")
    }
    return {
        val granted = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        if (granted) launchRecognition() else permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
    }
}
