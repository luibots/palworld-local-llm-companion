param(
    [ValidateRange(1, 10)]
    [int]$TimeoutSeconds = 4,
    [string]$WavePath = ''
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech

$phrases = @(
    'yes',
    'yes place them',
    'yeah',
    'yep',
    'sure',
    'okay',
    'do it',
    'place it',
    'place them',
    'put it on the map',
    'put them on the map',
    'mark it',
    'mark them',
    'no',
    'nope',
    'not now',
    'cancel',
    'do not',
    "don't"
)

$choices = [System.Speech.Recognition.Choices]::new()
$choices.Add([string[]]$phrases)
$grammarBuilder = [System.Speech.Recognition.GrammarBuilder]::new($choices)
$grammar = [System.Speech.Recognition.Grammar]::new($grammarBuilder)
$recognizer = [System.Speech.Recognition.SpeechRecognitionEngine]::new(
    [System.Globalization.CultureInfo]::GetCultureInfo('en-US')
)

try {
    $recognizer.LoadGrammar($grammar)
    if ($WavePath) {
        $recognizer.SetInputToWaveFile((Resolve-Path -LiteralPath $WavePath).Path)
    } else {
        $recognizer.SetInputToDefaultAudioDevice()
    }
    $result = $recognizer.Recognize([TimeSpan]::FromSeconds($TimeoutSeconds))
    if ($null -ne $result -and $result.Confidence -ge 0.55) {
        Write-Output $result.Text
    }
} finally {
    $recognizer.Dispose()
}
